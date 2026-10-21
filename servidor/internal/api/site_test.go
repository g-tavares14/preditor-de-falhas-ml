package api_test

import (
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"preditor/internal/configuracao"
)

func TestSite_cachePorTipoDeArquivo(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	escrever(t, filepath.Join(a.Site, "assets", "index-AbC123.js"), "export {};")
	escrever(t, filepath.Join(a.Site, "mapa", "countries-110m.json"), "{}")
	escrever(t, filepath.Join(a.Site, "dados", "replay.json"), "{}")
	escrever(t, filepath.Join(a.Site, "dados", "aovivo.json"), `{"meta":{}}`)

	casos := map[string]string{
		"/":                         "no-cache",                    // a porta de entrada: aponta para os arquivos novos
		"/testar":                   "no-cache",                    // outra tela do app, o mesmo index.html
		"/assets/index-AbC123.js":   "max-age=31536000, immutable", // o hash está no nome
		"/mapa/countries-110m.json": "max-age=86400",               // quase nunca muda
		"/dados/replay.json":        "max-age=300",                 // mantém o nome: cinco minutos
		"/dados/aovivo.json":        "no-cache",                    // regravado a cada minuto sem mudar de nome
	}
	for caminho, esperado := range casos {
		r := a.pedir(t, http.MethodGet, caminho, "", nil)
		if r.StatusCode != http.StatusOK {
			t.Errorf("%s: %d", caminho, r.StatusCode)
			continue
		}
		if got := r.Header.Get("Cache-Control"); !strings.Contains(got, esperado) {
			t.Errorf("%s: Cache-Control=%q, esperava conter %q", caminho, got, esperado)
		}
	}
	if tipo := a.pedir(t, http.MethodGet, "/assets/index-AbC123.js", "", nil).Header.Get("Content-Type"); !strings.Contains(tipo, "javascript") {
		t.Errorf("módulo ES precisa de Content-Type de JavaScript, veio %q", tipo)
	}
}

func TestSite_telasDoAppRecebemOIndexHtmlComACSP(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)

	for _, caminho := range []string{"/", "/testar", "/historico", "/historico/", "/testar?exemplo=pico", "/historico?pagina=2"} {
		r := a.pedir(t, http.MethodGet, caminho, "", nil)
		corpo, _ := io.ReadAll(r.Body)
		if r.StatusCode != http.StatusOK || !strings.Contains(string(corpo), "<title>mapa</title>") {
			t.Errorf("%s devia entregar o index.html: %d %q", caminho, r.StatusCode, corpo)
		}
		// A CSP vai por cabeçalho (o <meta> do index.html não existe mais): só a própria origem e nenhum <base>.
		if csp := r.Header.Get("Content-Security-Policy"); !strings.Contains(csp, "default-src 'self'") || !strings.Contains(csp, "base-uri 'none'") {
			t.Errorf("%s: Content-Security-Policy=%q", caminho, csp)
		}
	}
}

func TestSite_caminhoQueNaoEhDoAppNemArquivoDa404(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)

	for _, caminho := range []string{"/nao-existe", "/testar/outra", "/historico/1", "/api-falsa"} {
		r := a.pedir(t, http.MethodGet, caminho, "", nil)
		if r.StatusCode != http.StatusNotFound {
			t.Errorf("%s: esperava 404, veio %d", caminho, r.StatusCode)
		}
	}
}

func TestSite_404naoEhGuardadoEmCache(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)

	r := a.pedir(t, http.MethodGet, "/nao-existe.js", "", nil)

	if r.StatusCode != http.StatusNotFound {
		t.Fatalf("esperava 404, veio %d", r.StatusCode)
	}
	if got := r.Header.Get("Cache-Control"); got != "" {
		t.Errorf("um 404 com Cache-Control ficaria 5 min no CloudFront mesmo depois do arquivo aparecer: %q", got)
	}
}

func TestSite_naoListaPastasNemServeArquivoOculto(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)
	escrever(t, filepath.Join(a.Site, "vendor", "d3.min.js"), "// d3")
	escrever(t, filepath.Join(a.Site, ".DS_Store"), "segredo")
	escrever(t, filepath.Join(a.Site, "dados", ".env"), "SENHA=1")

	// Um arquivo FORA da pasta do site, ao lado dela: se algum caminho "../" escapar, o conteúdo aparece na resposta.
	escrever(t, filepath.Join(filepath.Dir(a.Site), "fora-do-site.txt"), "SEGREDO-DE-FORA")

	// Sem seguir redirecionamento: o ServeMux limpa `/../` com um 301 para o caminho limpo, e seguir esse 301 chegaria à index.html
	// (legítima) e pareceria um 200 indevido. `/%2e%2e/` vira `/` por `path.Clean` dentro do FileServer: serve a index.html do site.
	cliente := &http.Client{CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	for _, caminho := range []string{"/vendor/", "/vendor", "/dados/", "/.DS_Store", "/dados/.env", "/../etc/passwd", "/vendor/../.DS_Store",
		"/../fora-do-site.txt", "/%2e%2e/fora-do-site.txt", "/..%2ffora-do-site.txt", "/%2e%2e%2ffora-do-site.txt", "/vendor/%2e%2e/%2e%2e/fora-do-site.txt"} {
		r, err := cliente.Get(a.URL + caminho)
		if err != nil {
			t.Fatal(err)
		}
		corpo, _ := io.ReadAll(r.Body)
		r.Body.Close()
		if r.StatusCode == http.StatusOK || strings.Contains(string(corpo), "segredo") || strings.Contains(string(corpo), "SENHA") ||
			strings.Contains(string(corpo), "SEGREDO-DE-FORA") {
			t.Errorf("%s não devia ser servido: %d %q", caminho, r.StatusCode, corpo)
		}
	}
}

func TestAoVivo_saiDoArquivoConfigurado_eDa404EnquantoEleNaoExiste(t *testing.T) {
	arquivo := filepath.Join(t.TempDir(), "volume", "aovivo.json")
	a := novoAmbiente(t, novoModeloFalso(t).URL, func(c *configuracao.Configuracao) { c.ArquivoAoVivo = arquivo })

	if r := a.pedir(t, http.MethodGet, "/dados/aovivo.json", "", nil); r.StatusCode != http.StatusNotFound {
		t.Fatalf("sem o arquivo: esperava 404, veio %d", r.StatusCode)
	}

	escrever(t, arquivo, `{"meta":{"modo":"ao_vivo"}}`)
	r := a.pedir(t, http.MethodGet, "/dados/aovivo.json", "", nil)
	corpo, _ := io.ReadAll(r.Body)
	if r.StatusCode != http.StatusOK {
		t.Fatalf("com o arquivo: esperava 200, veio %d", r.StatusCode)
	}
	if !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
		t.Errorf("Content-Type: %q", r.Header.Get("Content-Type"))
	}
	if !strings.Contains(r.Header.Get("Cache-Control"), "no-cache") {
		t.Errorf("Cache-Control: %q", r.Header.Get("Cache-Control"))
	}
	if !strings.Contains(string(corpo), "ao_vivo") {
		t.Errorf("corpo: %s", corpo)
	}

	// O serviço regrava o arquivo inteiro; a próxima leitura já traz o conteúdo novo.
	if err := os.WriteFile(arquivo, []byte(`{"meta":{"modo":"outro"}}`), 0o644); err != nil {
		t.Fatal(err)
	}
	corpo, _ = io.ReadAll(a.pedir(t, http.MethodGet, "/dados/aovivo.json", "", nil).Body)
	if !strings.Contains(string(corpo), "outro") {
		t.Errorf("a leitura seguinte devia ver o arquivo novo: %s", corpo)
	}
}
