package api

import (
	"errors"
	"io"
	"mime"
	"net/http"
	"strconv"
	"time"

	"preditor/internal/banco"
	"preditor/internal/medicao"
	"preditor/internal/modelo"
	"preditor/internal/previsao"
)

const (
	tamanhoPadraoDaPagina = 20
	tamanhoMaximoDaPagina = 100
	mensagemDaPaginacao   = "'pagina' começa em 1 e 'tamanho' vai de 1 a 100."
	mensagemDaOrigem      = "'origem' tem de ser 'api' ou 'formulario'."
	mensagemDoTipoDeCorpo = "O corpo tem de ser application/json."
	mensagemDaValidacao   = "Há colunas com valor inválido."
	mensagemDoCorpoGrande = "O corpo passa do limite."
)

// previsaoResposta é a resposta pública de `POST /api/previsoes`. Os nomes são camelCase (como a API em C# sempre respondeu),
// enquanto as colunas da medição, em `entrada`, seguem os nomes do modelo (snake_case).
type previsaoResposta struct {
	ID             int64              `json:"id"`
	CriadaEmUtc    time.Time          `json:"criadaEmUtc"`
	Classe         string             `json:"classe"`
	Probabilidades map[string]float64 `json:"probabilidades"`
	ModeloSha256   string             `json:"modeloSha256"`
}

type itemDoHistorico struct {
	Previsao previsaoResposta `json:"previsao"`
	Entrada  medicao.Medicao  `json:"entrada"`
	Origem   string           `json:"origem"`
}

type paginaDePrevisoes struct {
	Pagina  int               `json:"pagina"`
	Tamanho int               `json:"tamanho"`
	Total   int               `json:"total"`
	Itens   []itemDoHistorico `json:"itens"`
}

func comoResposta(p banco.Previsao) previsaoResposta {
	return previsaoResposta{
		ID: p.ID, CriadaEmUtc: p.CriadaEmUTC, Classe: p.Classe, ModeloSha256: p.ModeloSHA256,
		Probabilidades: map[string]float64{"FALHA": p.ProbFalha, "OK": p.ProbOk, "RISCO": p.ProbRisco},
	}
}

type manipuladores struct {
	previsoes *previsao.Servico
	banco     *banco.Banco
	modelo    *modelo.Cliente
}

// criar: prevê a classe de uma rota 12 minutos à frente e guarda o resultado.
func (h *manipuladores) criar(w http.ResponseWriter, r *http.Request) {
	// Só JSON. Isto também fecha a porta do CSRF por formulário de outro site: um <form> não consegue enviar application/json.
	if tipo, _, err := mime.ParseMediaType(r.Header.Get("Content-Type")); err != nil || tipo != "application/json" {
		escreverProblema(w, problema{Title: mensagemDoTipoDeCorpo, Status: http.StatusUnsupportedMediaType})
		return
	}

	origem := previsao.OrigemAPI
	if pedida := r.URL.Query().Get("origem"); pedida != "" {
		if pedida != previsao.OrigemAPI && pedida != previsao.OrigemFormulario {
			escreverProblema(w, problema{Title: mensagemDaOrigem, Status: http.StatusBadRequest})
			return
		}
		origem = pedida
	}

	corpo, err := io.ReadAll(r.Body)
	if err != nil {
		var grande *http.MaxBytesError
		if errors.As(err, &grande) {
			// Corpo em pedaços, sem Content-Length: só descobrimos o excesso lendo. É 413, e não 400.
			escreverProblema(w, problema{Title: mensagemDoCorpoGrande, Status: http.StatusRequestEntityTooLarge})
			return
		}
		escreverProblema(w, problema{Title: "Não consegui ler o corpo do pedido.", Status: http.StatusBadRequest})
		return
	}

	m, err := medicao.Decodificar(corpo)
	if err != nil {
		escreverProblema(w, problema{Title: err.Error(), Status: http.StatusBadRequest})
		return
	}

	erros, gravada, err := h.previsoes.Prever(r.Context(), m, origem)
	if err != nil {
		falha(w, r, err)
		return
	}
	if gravada == nil {
		escreverProblema(w, problema{Title: mensagemDaValidacao, Status: http.StatusBadRequest, Errors: erros})
		return
	}
	escreverJSON(w, http.StatusOK, comoResposta(*gravada))
}

// listar: o histórico, da previsão mais nova para a mais antiga.
func (h *manipuladores) listar(w http.ResponseWriter, r *http.Request) {
	pagina, ok1 := inteiroDaConsulta(r, "pagina", 1)
	tamanho, ok2 := inteiroDaConsulta(r, "tamanho", tamanhoPadraoDaPagina)
	if !ok1 || !ok2 || pagina < 1 || tamanho < 1 || tamanho > tamanhoMaximoDaPagina {
		escreverProblema(w, problema{Title: mensagemDaPaginacao, Status: http.StatusBadRequest})
		return
	}

	linhas, total, err := h.banco.Listar(r.Context(), pagina, tamanho)
	if err != nil {
		falha(w, r, err)
		return
	}
	itens := make([]itemDoHistorico, 0, len(linhas))
	for _, p := range linhas {
		itens = append(itens, itemDoHistorico{Previsao: comoResposta(p), Entrada: p.Entrada, Origem: p.Origem})
	}
	escreverJSON(w, http.StatusOK, paginaDePrevisoes{Pagina: pagina, Tamanho: tamanho, Total: total, Itens: itens})
}

// inteiroDaConsulta lê `?nome=123`. Ausente = o padrão; escrito mas que não é inteiro = !ok (vira 400).
func inteiroDaConsulta(r *http.Request, nome string, padrao int) (int, bool) {
	texto := r.URL.Query().Get(nome)
	if texto == "" {
		return padrao, true
	}
	n, err := strconv.Atoi(texto)
	return n, err == nil
}

// ficha: a ficha do modelo carregado (família, parâmetros, colunas, classes, SHA-256), repassada como o Python a escreveu.
func (h *manipuladores) ficha(w http.ResponseWriter, r *http.Request) {
	ficha, err := h.modelo.Ficha(r.Context())
	if err != nil {
		falha(w, r, err)
		return
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Write(ficha)
}

// saude diz se a API está de pé e se o serviço do modelo também. Responde 200 nos dois casos; o campo diz qual está fora.
// O Compose usa este endereço como "a API está viva": o contêiner não deve ser reiniciado só porque o modelo caiu.
func (h *manipuladores) saude(w http.ResponseWriter, r *http.Request) {
	ficha, err := h.modelo.Ficha(r.Context())
	var indisponivel *modelo.IndisponivelErro
	switch {
	case err == nil:
		escreverJSON(w, http.StatusOK, map[string]any{"api": "ok", "modelo": "ok", "sha256": modelo.SHA256(ficha)})
	case errors.As(err, &indisponivel):
		escreverJSON(w, http.StatusOK, map[string]any{"api": "ok", "modelo": "fora do ar", "sha256": nil})
	default:
		falha(w, r, err)
	}
}
