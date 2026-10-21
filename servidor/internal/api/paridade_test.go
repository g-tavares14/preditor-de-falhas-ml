//go:build unix

package api_test

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"syscall"
	"testing"
	"time"

	"preditor/internal/configuracao"
)

// tolerancia é a da prova de paridade: o Go não pode mudar nada do que o modelo Python respondeu.
const tolerancia = 1e-9

// TestParidade_ComOModeloPythonDeVerdade é a prova de que o Go não muda nada: a API, falando com a Random Forest de verdade, devolve em
// cada linha da amostra (gerada por `uv run python -m preditor_analise.conferir_servico`, com as linhas de NaN) a mesma classe e as
// mesmas probabilidades que o modelo recarregado deu no Python.
func TestParidade_ComOModeloPythonDeVerdade(t *testing.T) {
	if testing.Short() {
		t.Skip("-short: a paridade sobe o serviço Python (leva alguns segundos)")
	}
	uv, err := exec.LookPath("uv")
	if err != nil {
		t.Skip("PULADO: o `uv` não está no PATH, então a paridade com o Python de verdade NÃO foi conferida")
	}
	raiz := raizDoRepositorio(t)
	url := subirServicoPython(t, uv, raiz)

	dados, err := os.ReadFile(filepath.Join("testdata", "paridade.json"))
	if err != nil {
		t.Fatal(err)
	}
	var amostra struct {
		ModeloSHA256 string `json:"modelo_sha256"`
		Linhas       []struct {
			Entrada  json.RawMessage `json:"entrada"`
			Esperado struct {
				Classe         string             `json:"classe"`
				Probabilidades map[string]float64 `json:"probabilidades"`
			} `json:"esperado"`
		} `json:"amostra"`
	}
	if err := json.Unmarshal(dados, &amostra); err != nil {
		t.Fatal(err)
	}
	if len(amostra.Linhas) < 300 {
		t.Fatalf("a amostra de paridade devia ter ~300 linhas, tem %d", len(amostra.Linhas))
	}

	a := novoAmbiente(t, url, func(c *configuracao.Configuracao) {
		c.PedidosPorMinuto = 1_000_000 // a amostra inteira passa pela API em poucos segundos
		c.ModeloPrazo = 30 * time.Second
	})

	var diferencas []string
	comNaN := 0
	classes := map[string]bool{}
	for i, linha := range amostra.Linhas {
		var entrada map[string]*float64
		if err := json.Unmarshal(linha.Entrada, &entrada); err != nil {
			t.Fatal(err)
		}
		if slices.ContainsFunc(mapValues(entrada), func(v *float64) bool { return v == nil }) {
			comNaN++
		}

		resposta := a.postar(t, string(linha.Entrada))
		corpo, _ := io.ReadAll(resposta.Body)
		if resposta.StatusCode != http.StatusOK {
			t.Fatalf("linha %d: %d %s", i, resposta.StatusCode, corpo)
		}
		var recebido struct {
			Classe         string             `json:"classe"`
			Probabilidades map[string]float64 `json:"probabilidades"`
		}
		if err := json.Unmarshal(corpo, &recebido); err != nil {
			t.Fatal(err)
		}

		classes[recebido.Classe] = true
		if recebido.Classe != linha.Esperado.Classe {
			diferencas = append(diferencas, fmt.Sprintf("linha %d: classe %s, esperava %s", i, recebido.Classe, linha.Esperado.Classe))
		}
		for nome, esperado := range linha.Esperado.Probabilidades {
			if delta := math.Abs(recebido.Probabilidades[nome] - esperado); delta > tolerancia {
				diferencas = append(diferencas, fmt.Sprintf("linha %d: %s difere em %.2e", i, nome, delta))
			}
		}
	}

	if len(diferencas) > 0 {
		t.Fatalf("%d diferenças em relação ao Python (primeiras: %v)", len(diferencas), diferencas[:min(5, len(diferencas))])
	}
	if comNaN < 100 {
		t.Errorf("a amostra devia ter ao menos 100 linhas com NaN, tem %d", comNaN)
	}
	if got := slices.Sorted(mapKeys(classes)); !slices.Equal(got, []string{"FALHA", "OK", "RISCO"}) {
		t.Errorf("a amostra devia cobrir as 3 classes, cobriu %v", got)
	}

	// A API devolve o SHA-256 do arquivo que o Python abriu; é o mesmo que a amostra registrou.
	ficha := lerJSON(t, a.pedir(t, http.MethodGet, "/api/modelo", "", nil))
	if sha := ficha["modelo"].(map[string]any)["sha256"]; sha != amostra.ModeloSHA256 {
		t.Errorf("sha256 do modelo: %v, a amostra registrou %v", sha, amostra.ModeloSHA256)
	}
	t.Logf("paridade: %d linhas (%d com NaN) iguais ao Python, tolerância %.0e", len(amostra.Linhas), comNaN, tolerancia)
}

func mapValues[K comparable, V any](m map[K]V) []V {
	var valores []V
	for _, v := range m {
		valores = append(valores, v)
	}
	return valores
}

func mapKeys[K comparable, V any](m map[K]V) func(func(K) bool) {
	return func(yield func(K) bool) {
		for k := range m {
			if !yield(k) {
				return
			}
		}
	}
}

// raizDoRepositorio sobe pastas até achar o pyproject.toml: o teste roda de servidor/internal/api/.
func raizDoRepositorio(t *testing.T) string {
	t.Helper()
	pasta, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	for {
		if _, err := os.Stat(filepath.Join(pasta, "pyproject.toml")); err == nil {
			return pasta
		}
		pai := filepath.Dir(pasta)
		if pai == pasta {
			t.Fatal("não achei o pyproject.toml acima de " + pasta)
		}
		pasta = pai
	}
}

// subirServicoPython sobe `uv run python -m preditor_servico.servico_modelo` numa porta livre e o derruba no fim do teste.
func subirServicoPython(t *testing.T, uv, raiz string) string {
	t.Helper()
	escuta, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	porta := escuta.Addr().(*net.TCPAddr).Port
	escuta.Close()

	cmd := exec.Command(uv, "run", "python", "-m", "preditor_servico.servico_modelo", "--porta", fmt.Sprint(porta))
	cmd.Dir = raiz
	// Grupo de processos próprio: o `uv` lança o Python como filho, e matar só o `uv` deixaria o serviço no ar depois do teste.
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
		cmd.Wait()
	})

	url := fmt.Sprintf("http://127.0.0.1:%d", porta)
	// O Python leva alguns segundos para importar o scikit-learn e abrir o modelo.
	limite := time.Now().Add(90 * time.Second)
	for time.Now().Before(limite) {
		if r, err := http.Get(url + "/saude"); err == nil {
			r.Body.Close()
			if r.StatusCode == http.StatusOK {
				return url
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatal("o serviço Python não respondeu ao /saude em 90 s")
	return ""
}
