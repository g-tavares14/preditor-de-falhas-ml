package api

import (
	"slices"

	"preditor/internal/banco"
	"preditor/internal/medicao"
)

// PadroesDeRota lista os padrões de /api/* que o servidor registra (para o teste conferir que o openapi.json descreve todos).
func PadroesDeRota() []string {
	var padroes []string
	for padrao := range rotasDaAPI(&manipuladores{}) {
		padroes = append(padroes, padrao)
	}
	slices.Sort(padroes)
	return padroes
}

// TiposDosSchemas liga cada schema do openapi.json ao tipo Go que a API lê ou escreve (para o teste conferir os campos dos dois).
var TiposDosSchemas = map[string]any{
	"Medicao":           medicao.Medicao{},
	"PrevisaoResposta":  previsaoResposta{},
	"ItemDoHistorico":   itemDoHistorico{},
	"PaginaDePrevisoes": paginaDePrevisoes{},
	"Saude":             saudeResposta{},
	"Problema":          problema{},
}

// ClassesDaResposta são as chaves de `probabilidades` na resposta.
func ClassesDaResposta() []string {
	var classes []string
	for classe := range comoResposta(banco.Previsao{}).Probabilidades {
		classes = append(classes, classe)
	}
	slices.Sort(classes)
	return classes
}
