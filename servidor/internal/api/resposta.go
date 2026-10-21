// Package api monta o servidor HTTP: as rotas /api/*, o limite de pedidos, o tamanho do corpo, os erros e o site estático.
package api

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"

	"preditor/internal/modelo"
)

// problema é o corpo de erro no formato RFC 9457 (`application/problem+json`). `Errors` só aparece na validação, com uma lista de
// mensagens por coluna (é onde a tela Testar procura o erro de cada campo).
type problema struct {
	Title  string              `json:"title"`
	Status int                 `json:"status"`
	Detail string              `json:"detail,omitempty"`
	Errors map[string][]string `json:"errors,omitempty"`
}

func escreverJSON(w http.ResponseWriter, status int, corpo any) {
	dados, err := json.Marshal(corpo)
	if err != nil {
		// Só acontece com um tipo que não sabemos serializar (erro nosso). Melhor um 500 limpo que um corpo pela metade.
		slog.Error("serializar a resposta", "erro", err)
		http.Error(w, "Erro interno.", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	w.Write(dados)
}

func escreverProblema(w http.ResponseWriter, p problema) {
	dados, _ := json.Marshal(p) // struct de campos simples: não falha
	w.Header().Set("Content-Type", "application/problem+json; charset=utf-8")
	w.WriteHeader(p.Status)
	w.Write(dados)
}

// falha traduz um erro do serviço de previsão: modelo fora do ar vira 503 com a nossa mensagem; o resto vira um 500 genérico,
// e o detalhe (que pode citar caminho de arquivo ou SQL) fica só no log do servidor.
func falha(w http.ResponseWriter, r *http.Request, err error) {
	var indisponivel *modelo.IndisponivelErro
	switch {
	case errors.As(err, &indisponivel):
		escreverProblema(w, problema{
			Title: "O serviço do modelo está indisponível.", Status: http.StatusServiceUnavailable,
			Detail: indisponivel.Mensagem, // escrita por nós, sem detalhe de rede
		})
	case errors.Is(err, context.Canceled):
		// O cliente desistiu no meio do pedido: não há para quem responder, e não é um erro do servidor.
	default:
		slog.Error("falha no pedido", "metodo", r.Method, "caminho", r.URL.Path, "erro", err)
		escreverProblema(w, problema{Title: "Erro interno.", Status: http.StatusInternalServerError})
	}
}
