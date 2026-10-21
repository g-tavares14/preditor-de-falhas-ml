package api_test

import (
	"encoding/json"
	"io"
	"net/http"
	"slices"
	"strings"
	"testing"

	"preditor/internal/api"
)

func TestOpenAPI_descreveExatamenteAsRotasDaAPI(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	var contrato struct {
		Paths map[string]map[string]json.RawMessage `json:"paths"`
	}
	corpo, _ := io.ReadAll(a.pedir(t, http.MethodGet, "/api/openapi.json", "", nil).Body)
	if err := json.Unmarshal(corpo, &contrato); err != nil {
		t.Fatalf("o openapi.json não é JSON: %v", err)
	}

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

	if r, _ := semRedirecionar.Get(a.URL + "/swagger"); r.StatusCode != http.StatusMovedPermanently || r.Header.Get("Location") != "/swagger/" {
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
	if !strings.Contains(csp, "default-src 'self'") || strings.Contains(csp, "script-src") && strings.Contains(csp, "unsafe") {
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
