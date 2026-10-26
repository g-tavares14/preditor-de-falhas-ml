package api_test

import (
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"

	"preditor/internal/configuracao"
)

const medicaoTipica = `{"z_robusto":6.0,"aumento_pct":45.0,"n5_moderado":1}`

func TestPedidoValido_devolveAClasseDoModelo_eGravaNoBanco(t *testing.T) {
	modelo := novoModeloFalso(t)
	a := novoAmbiente(t, modelo.URL)

	resposta := a.postar(t, medicaoTipica)

	if resposta.StatusCode != http.StatusOK {
		t.Fatalf("esperava 200, veio %d", resposta.StatusCode)
	}
	corpo := lerJSON(t, resposta)
	if corpo["classe"] != "RISCO" || corpo["modeloSha256"] != "abc" {
		t.Errorf("classe/sha256 errados: %v", corpo)
	}
	if p := corpo["probabilidades"].(map[string]any); p["RISCO"] != 0.7 {
		t.Errorf("a probabilidade do modelo tem de passar sem mudar: %v", p)
	}
	if n := a.contarNoBanco(t); n != 1 {
		t.Errorf("esperava 1 linha no banco, tem %d", n)
	}

	// O valor ausente chega ao modelo como null (e não como 0), e as 10 chaves vão sempre: imputar esconderia um timeout (RFC §8.3).
	corpos := modelo.corposRecebidos()
	if len(corpos) != 1 {
		t.Fatalf("o modelo devia receber 1 pedido, recebeu %d", len(corpos))
	}
	var enviado struct {
		Medicoes []map[string]*float64 `json:"medicoes"`
	}
	if err := json.Unmarshal([]byte(corpos[0]), &enviado); err != nil {
		t.Fatal(err)
	}
	linha := enviado.Medicoes[0]
	if len(linha) != 10 {
		t.Errorf("o modelo devia receber as 10 colunas, recebeu %d: %s", len(linha), corpos[0])
	}
	if valor, existe := linha["perda_pct"]; !existe || valor != nil {
		t.Errorf("perda_pct devia ir como null explícito, foi %v (existe=%v)", valor, existe)
	}
	if linha["z_robusto"] == nil || *linha["z_robusto"] != 6 {
		t.Errorf("z_robusto devia ir como 6, foi %v", linha["z_robusto"])
	}
	if modelo.semTamanho != 0 {
		t.Error("o corpo para o Python foi em pedaços (sem Content-Length): o serviço o recusaria com 411")
	}
}

func TestHistorico_listaDaMaisNovaParaAMaisAntiga(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	a.postar(t, `{"z_robusto":1.0}`)
	a.postar(t, `{"z_robusto":2.0}`)

	pagina := lerJSON(t, a.pedir(t, http.MethodGet, "/api/previsoes?pagina=1&tamanho=10", "", nil))

	if pagina["total"] != 2.0 {
		t.Fatalf("total: %v", pagina["total"])
	}
	itens := pagina["itens"].([]any)
	primeiro, segundo := itens[0].(map[string]any), itens[1].(map[string]any)
	if z := primeiro["entrada"].(map[string]any)["z_robusto"]; z != 2.0 {
		t.Errorf("o primeiro devia ser o mais novo (z=2), veio %v", z)
	}
	if z := segundo["entrada"].(map[string]any)["z_robusto"]; z != 1.0 {
		t.Errorf("o segundo devia ser o mais antigo (z=1), veio %v", z)
	}
	if primeiro["origem"] != "api" {
		t.Errorf("origem: %v", primeiro["origem"])
	}
	if _, ok := primeiro["previsao"].(map[string]any)["criadaEmUtc"].(string); !ok {
		t.Errorf("criadaEmUtc devia ser um texto de data: %v", primeiro["previsao"])
	}
}

func TestHistoricoVazio_devolveListaVazia_enaoNull(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)

	corpo, _ := io.ReadAll(a.pedir(t, http.MethodGet, "/api/previsoes", "", nil).Body)

	if !strings.Contains(string(corpo), `"itens":[]`) {
		t.Errorf(`o JSON devia ter "itens":[], veio %s`, corpo)
	}
}

func TestColunaForaDaFaixa_devolve400SemChamarOModeloNemGravar(t *testing.T) {
	for corpo, coluna := range map[string]string{
		`{"perda_pct":150}`:   "perda_pct",
		`{"timeout_atual":2}`: "timeout_atual",
		`{"n5_timeout":9}`:    "n5_timeout",
	} {
		t.Run(coluna, func(t *testing.T) {
			modelo := novoModeloFalso(t)
			a := novoAmbiente(t, modelo.URL)

			resposta := a.postar(t, corpo)

			if resposta.StatusCode != http.StatusBadRequest {
				t.Fatalf("esperava 400, veio %d", resposta.StatusCode)
			}
			erros, _ := lerJSON(t, resposta)["errors"].(map[string]any)
			if _, ok := erros[coluna]; !ok {
				t.Errorf("o erro devia citar %q: %v", coluna, erros)
			}
			if len(modelo.corposRecebidos()) != 0 {
				t.Error("o modelo não devia ser chamado com uma medição inválida")
			}
			if n := a.contarNoBanco(t); n != 0 {
				t.Errorf("nada devia ser gravado, há %d linhas", n)
			}
		})
	}
}

func TestCorpoTorto_devolve400(t *testing.T) {
	for nome, corpo := range map[string]string{
		"coluna que o modelo não usa": `{"rtt":10.0}`,
		"texto no lugar de número":    `{"z_robusto":"3"}`,
		"NaN não é JSON":              `{"z_robusto":NaN}`,
		"não é JSON":                  `{nao e json`,
		"null sozinho":                `null`,
		"dois objetos":                `{} {}`,
	} {
		t.Run(nome, func(t *testing.T) {
			a := novoAmbiente(t, novoModeloFalso(t).URL)
			resposta := a.postar(t, corpo)
			if resposta.StatusCode != http.StatusBadRequest {
				t.Fatalf("esperava 400, veio %d", resposta.StatusCode)
			}
			if n := a.contarNoBanco(t); n != 0 {
				t.Errorf("nada devia ser gravado, há %d linhas", n)
			}
		})
	}
}

func TestOutroTipoDeCorpo_devolve415(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	// É o que um <form> de outro site mandaria: um formulário não consegue enviar application/json.
	resposta := a.pedir(t, http.MethodPost, "/api/previsoes", "z_robusto=1", map[string]string{"Content-Type": "application/x-www-form-urlencoded"})
	if resposta.StatusCode != http.StatusUnsupportedMediaType {
		t.Fatalf("esperava 415, veio %d", resposta.StatusCode)
	}
}

func TestPostDeOutraOrigem_eRecusado(t *testing.T) {
	modelo := novoModeloFalso(t)
	a := novoAmbiente(t, modelo.URL)

	resposta := a.pedir(t, http.MethodPost, "/api/previsoes", medicaoTipica, map[string]string{
		"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site", "Origin": "https://exemplo.invalido",
	})

	if resposta.StatusCode != http.StatusForbidden {
		t.Fatalf("esperava 403, veio %d", resposta.StatusCode)
	}
	if tipo := resposta.Header.Get("Content-Type"); !strings.HasPrefix(tipo, "application/problem+json") {
		t.Errorf("o 403 devia ter o formato de erro da API, veio %q", tipo)
	}
	if len(modelo.corposRecebidos()) != 0 || a.contarNoBanco(t) != 0 {
		t.Error("um pedido recusado não pode chegar ao modelo nem ao banco")
	}
	// O mesmo pedido vindo do próprio site passa.
	if r := a.pedir(t, http.MethodPost, "/api/previsoes", medicaoTipica, map[string]string{"Content-Type": "application/json", "Sec-Fetch-Site": "same-origin"}); r.StatusCode != http.StatusOK {
		t.Errorf("same-origin devia passar, veio %d", r.StatusCode)
	}
}

func TestOrigem_vemDaConsultaEValeSoParaOsDoisValores(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	cab := map[string]string{"Content-Type": "application/json"}

	if r := a.pedir(t, http.MethodPost, "/api/previsoes?origem=formulario", `{"z_robusto":1}`, cab); r.StatusCode != http.StatusOK {
		t.Fatalf("origem=formulario: %d", r.StatusCode)
	}
	if r := a.pedir(t, http.MethodPost, "/api/previsoes?origem=hacker", `{"z_robusto":1}`, cab); r.StatusCode != http.StatusBadRequest {
		t.Fatalf("origem inventada devia dar 400, deu %d", r.StatusCode)
	}

	itens := lerJSON(t, a.pedir(t, http.MethodGet, "/api/previsoes", "", nil))["itens"].([]any)
	if len(itens) != 1 || itens[0].(map[string]any)["origem"] != "formulario" {
		t.Errorf("devia haver só a previsão do formulário: %v", itens)
	}
}

func TestModeloForaDoAr_devolve503_eNaoGrava(t *testing.T) {
	casos := map[string]func(*modeloFalso){
		"o modelo responde 500":      func(m *modeloFalso) { m.status = http.StatusInternalServerError },
		"o modelo derruba a conexão": func(m *modeloFalso) { m.derrubar = true },
	}
	for nome, ajuste := range casos {
		t.Run(nome, func(t *testing.T) {
			a := novoAmbiente(t, novoModeloFalso(t, ajuste).URL)

			resposta := a.postar(t, medicaoTipica)

			if resposta.StatusCode != http.StatusServiceUnavailable {
				t.Fatalf("esperava 503, veio %d", resposta.StatusCode)
			}
			if tipo := resposta.Header.Get("Content-Type"); !strings.HasPrefix(tipo, "application/problem+json") {
				t.Errorf("o erro devia ser problem+json, veio %q", tipo)
			}
			corpo, _ := io.ReadAll(resposta.Body)
			if strings.Contains(string(corpo), "127.0.0.1") {
				t.Errorf("a resposta vaza o endereço do serviço do modelo: %s", corpo)
			}
			if n := a.contarNoBanco(t); n != 0 {
				t.Errorf("serviço fora do ar nunca deixa uma linha no histórico, há %d", n)
			}
		})
	}
}

func TestModeloQueRespondeUmFormatoEstranho_eTratadoComoForaDoAr(t *testing.T) {
	// 200 com um JSON que não é "uma previsão + modelo.sha256" (por exemplo, o endereço errado apontando para outro serviço).
	for nome, resposta := range map[string]string{
		"nenhuma previsão":        `{"previsoes":[],"modelo":{"sha256":"abc"}}`,
		"sem o sha256":            `{"previsoes":[{"classe":"OK","probabilidades":{"FALHA":0,"OK":1,"RISCO":0}}]}`,
		"falta uma probabilidade": `{"previsoes":[{"classe":"OK","probabilidades":{"OK":1}}],"modelo":{"sha256":"abc"}}`,
		"não é JSON":              `<html>oi</html>`,
	} {
		t.Run(nome, func(t *testing.T) {
			estranho := novoModeloFalso(t, func(m *modeloFalso) { m.corpoDoPrever = resposta })
			a := novoAmbiente(t, estranho.URL)

			if r := a.postar(t, medicaoTipica); r.StatusCode != http.StatusServiceUnavailable {
				t.Fatalf("esperava 503, veio %d", r.StatusCode)
			}
			if n := a.contarNoBanco(t); n != 0 {
				t.Errorf("nada devia ser gravado, há %d linhas", n)
			}
		})
	}
}

func TestPedidosDemais_devolvem429_masOSiteNaoConta(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL, func(c *configuracao.Configuracao) { c.PedidosPorMinuto = 2 })

	var codigos []int
	for range 3 {
		codigos = append(codigos, a.postar(t, `{}`).StatusCode)
	}

	if codigos[0] != 200 || codigos[1] != 200 || codigos[2] != http.StatusTooManyRequests {
		t.Fatalf("esperava 200, 200, 429; veio %v", codigos)
	}
	if r := a.pedir(t, http.MethodGet, "/api/saude", "", nil); r.StatusCode != http.StatusTooManyRequests || r.Header.Get("Retry-After") == "" {
		t.Errorf("o limite vale para todas as rotas /api/* e diz quanto esperar; veio %d, Retry-After=%q", r.StatusCode, r.Header.Get("Retry-After"))
	}
	if r := a.pedir(t, http.MethodGet, "/", "", nil); r.StatusCode != http.StatusOK {
		t.Errorf("o site estático não entra no limite; veio %d", r.StatusCode)
	}
}

func TestCorpoGrandeDemais_eRecusadoCom413(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL, func(c *configuracao.Configuracao) { c.CorpoMaximoBytes = 100 })
	grande := `{"z_robusto":1.0,` + strings.Repeat(" ", 200) + `}`

	// Com Content-Length: recusado antes de ler.
	if r := a.postar(t, grande); r.StatusCode != http.StatusRequestEntityTooLarge {
		t.Errorf("com Content-Length: esperava 413, veio %d", r.StatusCode)
	}

	// Sem Content-Length (corpo em pedaços): só se descobre lendo. Tem de ser 413 também, e não 400.
	pedido, _ := http.NewRequest(http.MethodPost, a.URL+"/api/previsoes", io.NopCloser(strings.NewReader(grande)))
	pedido.Header.Set("Content-Type", "application/json")
	resposta, err := http.DefaultClient.Do(pedido)
	if err != nil {
		t.Fatal(err)
	}
	defer resposta.Body.Close()
	if resposta.StatusCode != http.StatusRequestEntityTooLarge {
		t.Errorf("em pedaços: esperava 413, veio %d", resposta.StatusCode)
	}
	if n := a.contarNoBanco(t); n != 0 {
		t.Errorf("nada devia ser gravado, há %d linhas", n)
	}
}

func TestSaude_dizQualParteEstaForaMasResponde200(t *testing.T) {
	noAr := novoAmbiente(t, novoModeloFalso(t).URL)
	fora := novoAmbiente(t, novoModeloFalso(t, func(m *modeloFalso) { m.derrubar = true }).URL)

	bem, mal := noAr.pedir(t, http.MethodGet, "/api/saude", "", nil), fora.pedir(t, http.MethodGet, "/api/saude", "", nil)

	if bem.StatusCode != 200 || mal.StatusCode != 200 {
		t.Fatalf("/api/saude responde 200 nos dois casos; veio %d e %d", bem.StatusCode, mal.StatusCode)
	}
	b, m := lerJSON(t, bem), lerJSON(t, mal)
	if b["modelo"] != "ok" || b["sha256"] != "abc" {
		t.Errorf("com o modelo no ar: %v", b)
	}
	if m["modelo"] != "fora do ar" || m["api"] != "ok" || m["sha256"] != nil {
		t.Errorf("com o modelo fora: %v", m)
	}
}

func TestModelo_repassaAFichaDoPythonSemMudar(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)

	ficha := lerJSON(t, a.pedir(t, http.MethodGet, "/api/modelo", "", nil))

	if ficha["modelo"].(map[string]any)["familia"] != "random_forest" {
		t.Errorf("a ficha devia ser a do Python: %v", ficha)
	}
}

func TestPaginaInvalidaDoHistorico_devolve400(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	for _, consulta := range []string{"pagina=0", "tamanho=101", "tamanho=0", "pagina=abc", "tamanho=-3"} {
		if r := a.pedir(t, http.MethodGet, "/api/previsoes?"+consulta, "", nil); r.StatusCode != http.StatusBadRequest {
			t.Errorf("?%s: esperava 400, veio %d", consulta, r.StatusCode)
		}
	}
}

func TestMetodoNaoPermitido_devolve405(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	if r := a.pedir(t, http.MethodDelete, "/api/previsoes", "", nil); r.StatusCode != http.StatusMethodNotAllowed {
		t.Errorf("esperava 405, veio %d", r.StatusCode)
	}
}

// Atrás do CloudFront o navegador manda `Origin: https://<cloudfront>`, mas o `Host` que chega ao servidor pode ser o da instância (a
// política de origem do CloudFront decide) e o `Sec-Fetch-Site` pode não ser repassado. Sem declarar a origem pública, o POST da tela
// Testar levaria 403 em produção. Este teste reproduz o caso, e `Web__OrigensConfiaveis` é a saída.
func TestPostAtrasDoCloudFront_precisaDeclararAOrigemPublica(t *testing.T) {
	const origemPublica = "https://d3csgsins36z0x.cloudfront.net"
	cabecalhos := map[string]string{"Content-Type": "application/json", "Origin": origemPublica} // sem Sec-Fetch-Site

	semDeclarar := novoAmbiente(t, novoModeloFalso(t).URL)
	if r := semDeclarar.pedir(t, http.MethodPost, "/api/previsoes", medicaoTipica, cabecalhos); r.StatusCode != http.StatusForbidden {
		t.Fatalf("sem declarar a origem pública, o Host (%s) não bate com o Origin: esperava 403, veio %d", semDeclarar.URL, r.StatusCode)
	}

	declarada := novoAmbiente(t, novoModeloFalso(t).URL, func(c *configuracao.Configuracao) { c.OrigensConfiaveis = []string{origemPublica} })
	if r := declarada.pedir(t, http.MethodPost, "/api/previsoes", medicaoTipica, cabecalhos); r.StatusCode != http.StatusOK {
		t.Fatalf("com a origem pública declarada o POST devia passar, veio %d", r.StatusCode)
	}
	// Declarar uma origem não abre a porta para as outras.
	outra := map[string]string{"Content-Type": "application/json", "Origin": "https://outro-site.invalido"}
	if r := declarada.pedir(t, http.MethodPost, "/api/previsoes", medicaoTipica, outra); r.StatusCode != http.StatusForbidden {
		t.Errorf("outra origem continua recusada: esperava 403, veio %d", r.StatusCode)
	}
}
