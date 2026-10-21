// Package modelo fala com o microserviço Python (`POST /prever`, `GET /saude`). Não calcula nada do modelo.
package modelo

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"

	"preditor/internal/medicao"
)

// IndisponivelErro é o microserviço não ter respondido como devia (fora do ar, lento, com erro ou com um formato que não é o esperado).
// Vira 503 na API. A mensagem é escrita aqui, sem detalhe de rede, e é a que o cliente lê.
type IndisponivelErro struct {
	Mensagem string
	Causa    error
}

func (e *IndisponivelErro) Error() string { return e.Mensagem }
func (e *IndisponivelErro) Unwrap() error { return e.Causa }

// Previsao é o que o Python devolve para uma medição: a classe 12 minutos à frente e as probabilidades.
type Previsao struct {
	Classe         string
	Probabilidades map[string]float64
	SHA256         string
}

// Maior resposta que aceitamos do Python. Uma previsão tem poucas centenas de bytes; mais que isto é um serviço que não é o esperado.
const tamanhoMaximoDaResposta = 1 << 20

type Cliente struct {
	base string
	http *http.Client
}

// NovoCliente: `base` é a URL do microserviço (ex.: http://127.0.0.1:8001) e `prazo` o tempo máximo de cada chamada.
func NovoCliente(base string, prazo time.Duration) *Cliente {
	return &Cliente{base: strings.TrimRight(base, "/"), http: &http.Client{Timeout: prazo}}
}

type respostaDoPrever struct {
	Previsoes []struct {
		Classe         string             `json:"classe"`
		Probabilidades map[string]float64 `json:"probabilidades"`
	} `json:"previsoes"`
	Modelo *struct {
		SHA256 string `json:"sha256"`
	} `json:"modelo"`
}

// Prever manda uma medição e devolve a previsão. Uma medição enviada = uma previsão de volta; qualquer outra coisa é
// um serviço que não é o que esperamos.
func (c *Cliente) Prever(ctx context.Context, m medicao.Medicao) (Previsao, error) {
	// O corpo vai pronto, em bytes: o `bytes.Reader` faz o cliente enviar `Content-Length`, e o serviço Python exige o tamanho
	// para recusar corpos grandes antes de ler (411 sem ele). Um corpo em pedaços (chunked) seria recusado.
	corpo, err := json.Marshal(map[string][]medicao.Medicao{"medicoes": {m}})
	if err != nil {
		return Previsao{}, err // medição validada não falha aqui; se falhar é erro nosso (500), não do modelo
	}
	dados, err := c.chamar(ctx, http.MethodPost, "/prever", bytes.NewReader(corpo))
	if err != nil {
		return Previsao{}, err
	}

	var resposta respostaDoPrever
	if err := json.Unmarshal(dados, &resposta); err != nil {
		return Previsao{}, &IndisponivelErro{"O serviço do modelo devolveu algo que não é JSON.", err}
	}
	if len(resposta.Previsoes) != 1 || resposta.Modelo == nil || resposta.Modelo.SHA256 == "" {
		return Previsao{}, &IndisponivelErro{Mensagem: "O serviço do modelo respondeu num formato inesperado."}
	}
	p := resposta.Previsoes[0]
	if p.Classe == "" {
		return Previsao{}, &IndisponivelErro{Mensagem: "O serviço do modelo respondeu num formato inesperado."}
	}
	// O banco guarda uma coluna por classe: faltar uma probabilidade é um serviço que não é o que esperamos.
	for _, classe := range []string{"FALHA", "OK", "RISCO"} {
		if _, ok := p.Probabilidades[classe]; !ok {
			return Previsao{}, &IndisponivelErro{Mensagem: "O serviço do modelo respondeu num formato inesperado."}
		}
	}
	return Previsao{Classe: p.Classe, Probabilidades: p.Probabilidades, SHA256: resposta.Modelo.SHA256}, nil
}

// Ficha é a resposta do `/saude` do Python como JSON cru: é o que `/api/modelo` mostra (a ficha do modelo carregado).
func (c *Cliente) Ficha(ctx context.Context) (json.RawMessage, error) {
	dados, err := c.chamar(ctx, http.MethodGet, "/saude", nil)
	if err != nil {
		return nil, err
	}
	if !json.Valid(dados) {
		return nil, &IndisponivelErro{Mensagem: "O serviço do modelo devolveu algo que não é JSON."}
	}
	return dados, nil
}

// SHA256 tira da ficha o SHA-256 do arquivo que o Python abriu.
func SHA256(ficha json.RawMessage) string {
	var f struct {
		Modelo struct {
			SHA256 string `json:"sha256"`
		} `json:"modelo"`
	}
	_ = json.Unmarshal(ficha, &f) // ficha sem o campo = texto vazio; quem chama decide o que fazer
	return f.Modelo.SHA256
}

func (c *Cliente) chamar(ctx context.Context, metodo, caminho string, corpo io.Reader) ([]byte, error) {
	pedido, err := http.NewRequestWithContext(ctx, metodo, c.base+caminho, corpo)
	if err != nil {
		return nil, &IndisponivelErro{"A URL do serviço do modelo é inválida.", err}
	}
	if corpo != nil {
		pedido.Header.Set("Content-Type", "application/json")
	}

	resposta, err := c.http.Do(pedido)
	if err != nil {
		// Quem desistiu foi o cliente da nossa API: não é falha do modelo, e a mensagem de 503 seria mentira.
		if errors.Is(ctx.Err(), context.Canceled) {
			return nil, ctx.Err()
		}
		var urlErr *url.Error
		if errors.As(err, &urlErr) && urlErr.Timeout() {
			return nil, &IndisponivelErro{"O serviço do modelo demorou demais para responder.", err}
		}
		return nil, &IndisponivelErro{"Não consegui falar com o serviço do modelo.", err}
	}
	defer resposta.Body.Close()

	if resposta.StatusCode < 200 || resposta.StatusCode > 299 {
		return nil, &IndisponivelErro{Mensagem: "O serviço do modelo respondeu " + strconv.Itoa(resposta.StatusCode) + "."}
	}
	dados, err := io.ReadAll(io.LimitReader(resposta.Body, tamanhoMaximoDaResposta+1))
	if err != nil {
		return nil, &IndisponivelErro{"A resposta do serviço do modelo foi interrompida.", err}
	}
	if len(dados) > tamanhoMaximoDaResposta {
		return nil, &IndisponivelErro{Mensagem: "O serviço do modelo respondeu algo grande demais."}
	}
	if len(bytes.TrimSpace(dados)) == 0 {
		return nil, &IndisponivelErro{Mensagem: "O serviço do modelo devolveu uma resposta vazia."}
	}
	return dados, nil
}
