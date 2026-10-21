package api_test

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"preditor/internal/api"
	"preditor/internal/banco"
	"preditor/internal/configuracao"
	"preditor/internal/modelo"
	"preditor/internal/previsao"
)

// modeloFalso é um "microserviço do modelo" de mentira: devolve sempre a mesma classe, ou falha, conforme o teste pede.
type modeloFalso struct {
	*httptest.Server
	status   int    // status HTTP das respostas (0 = 200)
	classe   string // "" = RISCO
	derrubar bool   // fecha a conexão sem responder
	// corpoDoPrever, se preenchido, é a resposta do /prever palavra por palavra (para testar um serviço que responde algo estranho).
	corpoDoPrever string

	mu         sync.Mutex
	corpos     []string
	semTamanho int // quantos POST chegaram sem Content-Length (em pedaços): o serviço Python os recusa com 411
	pedidos    int
}

func novoModeloFalso(t *testing.T, ajustar ...func(*modeloFalso)) *modeloFalso {
	t.Helper()
	m := &modeloFalso{}
	for _, f := range ajustar {
		f(m)
	}
	m.Server = httptest.NewServer(http.HandlerFunc(m.atender))
	t.Cleanup(m.Server.Close)
	return m
}

func (m *modeloFalso) atender(w http.ResponseWriter, r *http.Request) {
	m.mu.Lock()
	m.pedidos++
	m.mu.Unlock()
	if m.derrubar {
		conexao, _, err := w.(http.Hijacker).Hijack()
		if err == nil {
			conexao.Close()
		}
		return
	}
	if r.Method == http.MethodPost {
		corpo, _ := io.ReadAll(r.Body)
		m.mu.Lock()
		m.corpos = append(m.corpos, string(corpo))
		if r.ContentLength < 0 {
			m.semTamanho++
		}
		m.mu.Unlock()
	}
	classe := m.classe
	if classe == "" {
		classe = "RISCO"
	}
	w.Header().Set("Content-Type", "application/json")
	if m.status != 0 {
		w.WriteHeader(m.status)
	}
	if r.URL.Path == "/saude" {
		io.WriteString(w, `{"status":"ok","modelo":{"familia":"random_forest","sha256":"abc","classes":["FALHA","OK","RISCO"]}}`)
		return
	}
	if m.corpoDoPrever != "" {
		io.WriteString(w, m.corpoDoPrever)
		return
	}
	json.NewEncoder(w).Encode(map[string]any{
		"previsoes": []any{map[string]any{"classe": classe, "probabilidades": map[string]float64{"FALHA": 0.1, "OK": 0.2, "RISCO": 0.7}}},
		"modelo":    map[string]string{"sha256": "abc"},
	})
}

func (m *modeloFalso) corposRecebidos() []string {
	m.mu.Lock()
	defer m.mu.Unlock()
	return append([]string(nil), m.corpos...)
}

// ambiente é a API inteira de pé, com um banco SQLite temporário e uma pasta de site temporária.
type ambiente struct {
	URL   string
	Banco *banco.Banco
	Site  string // a pasta do site
	cli   *http.Client
}

func novoAmbiente(t *testing.T, urlDoModelo string, ajustar ...func(*configuracao.Configuracao)) *ambiente {
	t.Helper()
	pasta := t.TempDir()
	site := filepath.Join(pasta, "site")
	escrever(t, filepath.Join(site, "index.html"), "<!doctype html><title>mapa</title>")

	cfg := configuracao.Padrao()
	cfg.ModeloURL = urlDoModelo
	cfg.ArquivoBanco = filepath.Join(pasta, "dados", "teste.db")
	cfg.PastaDoSite = site
	for _, f := range ajustar {
		f(&cfg)
	}

	bd, err := banco.Abrir(cfg.ArquivoBanco)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { bd.Fechar() })
	cliente := modelo.NovoCliente(cfg.ModeloURL, cfg.ModeloPrazo)
	manipulador, err := api.Novo(api.Dependencias{
		Config:    cfg,
		Previsoes: &previsao.Servico{Modelo: cliente, Banco: bd},
		Banco:     bd,
		Modelo:    cliente,
	})
	if err != nil {
		t.Fatal(err)
	}
	srv := httptest.NewServer(manipulador)
	t.Cleanup(srv.Close)
	return &ambiente{URL: srv.URL, Banco: bd, Site: site, cli: srv.Client()}
}

func escrever(t *testing.T, caminho, conteudo string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(caminho), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(caminho, []byte(conteudo), 0o644); err != nil {
		t.Fatal(err)
	}
}

// postar manda um POST /api/previsoes com Content-Type JSON.
func (a *ambiente) postar(t *testing.T, corpo string) *http.Response {
	t.Helper()
	return a.pedir(t, http.MethodPost, "/api/previsoes", corpo, map[string]string{"Content-Type": "application/json"})
}

func (a *ambiente) pedir(t *testing.T, metodo, caminho, corpo string, cabecalhos map[string]string) *http.Response {
	t.Helper()
	var leitor io.Reader
	if corpo != "" {
		leitor = strings.NewReader(corpo)
	}
	pedido, err := http.NewRequest(metodo, a.URL+caminho, leitor)
	if err != nil {
		t.Fatal(err)
	}
	for k, v := range cabecalhos {
		pedido.Header.Set(k, v)
	}
	resposta, err := a.cli.Do(pedido)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { resposta.Body.Close() })
	return resposta
}

// lerJSON decodifica o corpo da resposta num mapa.
func lerJSON(t *testing.T, r *http.Response) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.NewDecoder(r.Body).Decode(&m); err != nil {
		t.Fatalf("o corpo não é um objeto JSON: %v", err)
	}
	return m
}

func (a *ambiente) contarNoBanco(t *testing.T) int {
	t.Helper()
	_, total, err := a.Banco.Listar(t.Context(), 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	return total
}
