package api_test

import (
	"encoding/json"
	"io"
	"maps"
	"net/http"
	"reflect"
	"regexp"
	"slices"
	"strconv"
	"strings"
	"testing"

	"preditor/internal/api"
	"preditor/internal/configuracao"
	"preditor/internal/medicao"
)

// schema é o pedaço de um schema do openapi.json que os testes conferem.
type schema struct {
	Required   []string                   `json:"required"`
	Properties map[string]json.RawMessage `json:"properties"`
}

// contratoServido é o openapi.json como o servidor o entrega em /api/openapi.json, já decodificado (e o texto cru, para procurar $ref).
type contratoServido struct {
	Info struct {
		Description string `json:"description"`
	} `json:"info"`
	Paths      map[string]map[string]json.RawMessage `json:"paths"`
	Components struct {
		Schemas   map[string]schema          `json:"schemas"`
		Responses map[string]json.RawMessage `json:"responses"`
	} `json:"components"`
	texto string
}

func lerContrato(t *testing.T) contratoServido {
	t.Helper()
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	corpo, _ := io.ReadAll(a.pedir(t, http.MethodGet, "/api/openapi.json", "", nil).Body)
	var c contratoServido
	if err := json.Unmarshal(corpo, &c); err != nil {
		t.Fatalf("o openapi.json não é JSON: %v", err)
	}
	c.texto = string(corpo)
	return c
}

func TestOpenAPI_descreveExatamenteAsRotasDaAPI(t *testing.T) {
	contrato := lerContrato(t)

	var descritas []string
	for caminho, metodos := range contrato.Paths {
		for metodo := range metodos {
			descritas = append(descritas, strings.ToUpper(metodo)+" "+caminho)
		}
	}
	// O próprio /api/openapi.json não precisa se descrever; todas as outras rotas, sim. Rota nova sem contrato quebra aqui.
	var reais []string
	for _, padrao := range api.PadroesDeRota() {
		if padrao != "GET /api/openapi.json" {
			reais = append(reais, padrao)
		}
	}
	slices.Sort(descritas)
	slices.Sort(reais)
	if !slices.Equal(descritas, reais) {
		t.Errorf("o openapi.json e as rotas divergem:\n  contrato: %v\n  rotas:    %v", descritas, reais)
	}
}

func TestSwagger_publicaAInterfaceLocalSemCDN(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	semRedirecionar := &http.Client{CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}

	if r, _ := semRedirecionar.Get(a.URL + "/swagger"); r.StatusCode != http.StatusTemporaryRedirect || r.Header.Get("Location") != "/swagger/" {
		t.Errorf("/swagger devia redirecionar para /swagger/: %d %q", r.StatusCode, r.Header.Get("Location"))
	}

	pagina := a.pedir(t, http.MethodGet, "/swagger/", "", nil)
	html, _ := io.ReadAll(pagina.Body)
	if pagina.StatusCode != http.StatusOK || !strings.Contains(string(html), "swagger-ui-bundle.js") {
		t.Fatalf("/swagger/ devia servir a interface: %d %s", pagina.StatusCode, html)
	}
	if strings.Contains(string(html), "http://") || strings.Contains(string(html), "https://") {
		t.Errorf("a página do Swagger não pode chamar nada de fora (sem CDN): %s", html)
	}
	csp := pagina.Header.Get("Content-Security-Policy")
	// Só o estilo pode ser frouxo: a página não declara `script-src`, então o script segue o `default-src 'self'`.
	if !strings.Contains(csp, "default-src 'self'") || strings.Contains(csp, "script-src") {
		t.Errorf("CSP do Swagger: %q", csp)
	}

	for _, arquivo := range []string{"/swagger/swagger-ui-bundle.js", "/swagger/swagger-ui.css", "/swagger/iniciar.js"} {
		if r := a.pedir(t, http.MethodGet, arquivo, "", nil); r.StatusCode != http.StatusOK {
			t.Errorf("%s: %d", arquivo, r.StatusCode)
		}
	}
	if tipo := a.pedir(t, http.MethodGet, "/swagger/swagger-ui-bundle.js", "", nil).Header.Get("Content-Type"); !strings.Contains(tipo, "javascript") {
		t.Errorf("Content-Type do bundle: %q", tipo)
	}
}

// camposJSON lê as tags `json` de uma struct: o nome de cada campo e se ele some quando vazio (`omitempty`).
func camposJSON(tipo reflect.Type) (nomes, obrigatorios []string) {
	for campo := range tipo.Fields() {
		nome, opcoes, _ := strings.Cut(campo.Tag.Get("json"), ",")
		if nome == "-" || !campo.IsExported() {
			continue
		}
		nomes = append(nomes, nome)
		if !strings.Contains(opcoes, "omitempty") {
			obrigatorios = append(obrigatorios, nome)
		}
	}
	slices.Sort(nomes)
	slices.Sort(obrigatorios)
	return nomes, obrigatorios
}

// O contrato é escrito à mão: sem este teste, um campo novo (ou renomeado) numa struct deixaria o Swagger descrevendo outra API.
func TestOpenAPI_schemasTemOsCamposDasStructs(t *testing.T) {
	contrato := lerContrato(t)
	for nome, valor := range api.TiposDosSchemas {
		s, ok := contrato.Components.Schemas[nome]
		if !ok {
			t.Errorf("o openapi.json não tem o schema %s", nome)
			continue
		}
		campos, obrigatorios := camposJSON(reflect.TypeOf(valor))
		if descritos := slices.Sorted(maps.Keys(s.Properties)); !slices.Equal(descritos, campos) {
			t.Errorf("%s: o contrato descreve %v, a struct tem %v", nome, descritos, campos)
		}
		// A medição chega com qualquer coluna ausente, então nenhuma é obrigatória no contrato. Nas respostas, todo campo sem
		// `omitempty` sempre sai, e só ele.
		if nome == "Medicao" {
			obrigatorios = nil
		}
		if exigidos := slices.Sorted(slices.Values(s.Required)); !slices.Equal(exigidos, obrigatorios) {
			t.Errorf("%s: o contrato exige %v, a struct sempre escreve %v", nome, exigidos, obrigatorios)
		}
	}

	probabilidades := contrato.Components.Schemas["Probabilidades"]
	classes := api.ClassesDaResposta()
	if !slices.Equal(slices.Sorted(maps.Keys(probabilidades.Properties)), classes) || !slices.Equal(slices.Sorted(slices.Values(probabilidades.Required)), classes) {
		t.Errorf("Probabilidades: o contrato descreve %v (exige %v), a resposta tem %v", slices.Sorted(maps.Keys(probabilidades.Properties)), probabilidades.Required, classes)
	}
}

// Todo `$ref` aponta para um schema ou uma resposta que existe (o Swagger UI só mostra o erro ao abrir a rota).
func TestOpenAPI_referenciasExistem(t *testing.T) {
	contrato := lerContrato(t)
	for _, ref := range regexp.MustCompile(`"\$ref":\s*"([^"]+)"`).FindAllStringSubmatch(contrato.texto, -1) {
		alvo := ref[1]
		_, eSchema := contrato.Components.Schemas[strings.TrimPrefix(alvo, "#/components/schemas/")]
		_, eResposta := contrato.Components.Responses[strings.TrimPrefix(alvo, "#/components/responses/")]
		if !(strings.HasPrefix(alvo, "#/components/schemas/") && eSchema) && !(strings.HasPrefix(alvo, "#/components/responses/") && eResposta) {
			t.Errorf("$ref sem destino: %s", alvo)
		}
	}
}

// O exemplo do POST é o que o Swagger UI põe no "Try it out": ele tem de ser uma medição que a API aceita.
func TestOpenAPI_exemploDoPostEValido(t *testing.T) {
	contrato := lerContrato(t)
	var post struct {
		RequestBody struct {
			Content map[string]struct {
				Example json.RawMessage `json:"example"`
			} `json:"content"`
		} `json:"requestBody"`
	}
	if err := json.Unmarshal(contrato.Paths["/api/previsoes"]["post"], &post); err != nil {
		t.Fatal(err)
	}
	exemplo := post.RequestBody.Content["application/json"].Example
	m, err := medicao.Decodificar(exemplo)
	if err != nil {
		t.Fatalf("o exemplo não decodifica: %v (%s)", err, exemplo)
	}
	if erros := medicao.Validar(m); len(erros) > 0 {
		t.Errorf("o exemplo não passa na validação: %v", erros)
	}
}

// Os limites aparecem no texto do contrato; os números têm de ser os padrões de `configuracao.Padrao()`.
func TestOpenAPI_limitesSaoOsPadroes(t *testing.T) {
	contrato := lerContrato(t)
	padrao := configuracao.Padrao()
	if esperado := strconv.Itoa(padrao.PedidosPorMinuto) + " por minuto"; !strings.Contains(contrato.Info.Description, esperado) {
		t.Errorf("a descrição devia dizer %q", esperado)
	}
	if esperado := milhar(padrao.CorpoMaximoBytes) + " bytes"; !strings.Contains(string(contrato.Paths["/api/previsoes"]["post"]), esperado) {
		t.Errorf("o 413 do POST devia dizer %q", esperado)
	}
}

// milhar escreve um inteiro com ponto a cada três casas, como no texto do contrato (16384 → "16.384").
func milhar(n int64) string {
	texto := strconv.FormatInt(n, 10)
	for i := len(texto) - 3; i > 0; i -= 3 {
		texto = texto[:i] + "." + texto[i:]
	}
	return texto
}
