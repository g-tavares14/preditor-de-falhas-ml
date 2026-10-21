package api

import "slices"

// PadroesDeRota lista os padrões de /api/* que o servidor registra (para o teste conferir que o openapi.json descreve todos).
func PadroesDeRota() []string {
	var padroes []string
	for padrao := range rotasDaAPI(&manipuladores{}) {
		padroes = append(padroes, padrao)
	}
	slices.Sort(padroes)
	return padroes
}
