// Package medicao define as 10 colunas que a Random Forest recebe, como chegam pela API, e confere as faixas delas.
package medicao

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
)

// Medicao são as mesmas 10 colunas de `DadosModelo.colunas_ajustadas()`, na ordem do modelo.
//
// Valor ausente fica ausente: o campo é ponteiro (nil = null no JSON) e NÃO tem `omitempty`, então o Python sempre recebe as 10 chaves,
// as ausentes como `null` explícito. O modelo aceita NaN, e imputar um zero esconderia um timeout (RFC §8.3).
type Medicao struct {
	ZRobusto       *float64 `json:"z_robusto"`
	AumentoPct     *float64 `json:"aumento_pct"`
	JitterRelativo *float64 `json:"jitter_relativo"`
	PerdaPct       *float64 `json:"perda_pct"`
	TimeoutAtual   *float64 `json:"timeout_atual"`
	N5Timeout      *float64 `json:"n5_timeout"`
	N5Aumento80    *float64 `json:"n5_aumento80"`
	N5Moderado     *float64 `json:"n5_moderado"`
	Min5Z          *float64 `json:"min5_z"`
	Media5Z        *float64 `json:"media5_z"`
}

// Coluna junta o nome que o modelo conhece ao valor recebido (nil = ausente).
type Coluna struct {
	Nome  string
	Valor *float64
}

// Colunas devolve as 10 colunas na ordem do modelo, para quem precisa percorrê-las (a validação).
func (m Medicao) Colunas() []Coluna {
	return []Coluna{
		{"z_robusto", m.ZRobusto},
		{"aumento_pct", m.AumentoPct},
		{"jitter_relativo", m.JitterRelativo},
		{"perda_pct", m.PerdaPct},
		{"timeout_atual", m.TimeoutAtual},
		{"n5_timeout", m.N5Timeout},
		{"n5_aumento80", m.N5Aumento80},
		{"n5_moderado", m.N5Moderado},
		{"min5_z", m.Min5Z},
		{"media5_z", m.Media5Z},
	}
}

// FormatoInvalidoErro é um corpo que não é uma medição (JSON torto, coluna desconhecida, texto no lugar de número...).
// A mensagem é escrita aqui e vai para o cliente; nunca repassa o texto cru do `encoding/json`, que cita tipos do Go.
type FormatoInvalidoErro struct{ Mensagem string }

func (e *FormatoInvalidoErro) Error() string { return e.Mensagem }

// Decodificar lê o corpo de `POST /api/previsoes` com rigor: coluna que o modelo não usa é recusada (e não ignorada em silêncio),
// número tem de chegar como número (o `"3"` entre aspas não vale), e o corpo é um objeto só, sem nada depois dele.
func Decodificar(corpo []byte) (Medicao, error) {
	var m Medicao
	if bytes.Equal(bytes.TrimSpace(corpo), []byte("null")) {
		// `null` sozinho decodificaria "com sucesso" para uma medição toda ausente; é um corpo vazio disfarçado.
		return m, &FormatoInvalidoErro{"O corpo tem de ser um objeto JSON com as colunas da medição."}
	}

	decodificador := json.NewDecoder(bytes.NewReader(corpo))
	decodificador.DisallowUnknownFields()
	if err := decodificador.Decode(&m); err != nil {
		return Medicao{}, traduzir(err)
	}
	// Depois do objeto só pode haver espaço: um segundo valor (`{} {}`) ou lixo é recusado.
	if _, err := decodificador.Token(); !errors.Is(err, io.EOF) {
		return Medicao{}, &FormatoInvalidoErro{"O corpo tem de ser um único objeto JSON."}
	}
	return m, nil
}

func traduzir(err error) error {
	var tipo *json.UnmarshalTypeError
	var sintaxe *json.SyntaxError
	switch {
	case errors.As(err, &tipo) && tipo.Field != "":
		return &FormatoInvalidoErro{fmt.Sprintf("A coluna %q tem de ser um número ou null.", tipo.Field)}
	case errors.As(err, &tipo):
		return &FormatoInvalidoErro{"O corpo tem de ser um objeto JSON com as colunas da medição."}
	case errors.As(err, &sintaxe), errors.Is(err, io.ErrUnexpectedEOF), errors.Is(err, io.EOF):
		return &FormatoInvalidoErro{"O corpo não é um JSON válido."}
	default:
		// "json: unknown field "rtt"" é seguro e útil: cita só o que o próprio cliente mandou.
		return &FormatoInvalidoErro{err.Error()}
	}
}
