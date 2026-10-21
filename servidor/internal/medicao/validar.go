package medicao

import (
	"math"
	"strconv"
)

// JanelaDeMedicoes é `config.JANELA`: as colunas n5_* contam entre 0 e 5 medições.
const JanelaDeMedicoes = 5

// Regra confere o valor de uma coluna que chegou (coluna ausente nem passa por aqui) e devolve a mensagem de erro,
// ou "" se o valor é aceito. A mensagem vai direto para o cliente da API e para a tela Testar.
type Regra func(valor float64) string

// regras diz qual regra vale para cada coluna. O microserviço do modelo só confere o formato; as faixas ficam aqui, na borda pública.
var regras = map[string]Regra{
	"perda_pct":     faixa(0, 100),
	"timeout_atual": binaria(),
	"n5_timeout":    inteiro(0, JanelaDeMedicoes),
	"n5_aumento80":  inteiro(0, JanelaDeMedicoes),
	"n5_moderado":   inteiro(0, JanelaDeMedicoes),
	// As demais são métricas relativas sem teto fixo; só têm de ser números finitos.
	"z_robusto":       finito(),
	"aumento_pct":     finito(),
	"jitter_relativo": finito(),
	"min5_z":          finito(),
	"media5_z":        finito(),
}

// Validar devolve os erros por coluna (mapa vazio = medição válida), no formato `errors` da resposta 400 da API.
// Valor ausente (nil) é sempre válido: o modelo o aceita.
func Validar(m Medicao) map[string][]string {
	erros := map[string][]string{}
	for _, coluna := range m.Colunas() {
		if coluna.Valor == nil {
			continue
		}
		if mensagem := regras[coluna.Nome](*coluna.Valor); mensagem != "" {
			erros[coluna.Nome] = []string{mensagem}
		}
	}
	return erros
}

// As quatro regras. Todas escrevem a condição de ACEITAR e devolvem erro no resto: assim NaN e ±Infinito caem fora sem tratamento
// à parte (toda comparação com NaN dá falso, e `if v < min || v > max` o deixaria passar).

const (
	mensagemFinito  = "Tem de ser um número finito ou null."
	mensagemBinaria = "Tem de ser 0 ou 1."
)

// finito aceita qualquer número que não seja NaN nem ±Infinito.
func finito() Regra {
	return func(valor float64) string {
		if math.IsNaN(valor) || math.IsInf(valor, 0) {
			return mensagemFinito
		}
		return ""
	}
}

// faixa aceita números finitos de min a max, inclusive os dois extremos.
func faixa(min, max float64) Regra {
	mensagem := "Tem de estar entre " + numero(min) + " e " + numero(max) + "."
	return func(valor float64) string {
		if valor >= min && valor <= max { // falso para NaN; ±Infinito ficam fora dos limites
			return ""
		}
		return mensagem
	}
}

// binaria aceita só 0 ou 1.
func binaria() Regra {
	return func(valor float64) string {
		if valor == 0 || valor == 1 {
			return ""
		}
		return mensagemBinaria
	}
}

// inteiro aceita só números inteiros (2 e 2.0 sim, 2.5 não) de min a max, inclusive.
func inteiro(min, max int) Regra {
	mensagem := "Tem de ser um inteiro de " + strconv.Itoa(min) + " a " + strconv.Itoa(max) + "."
	return func(valor float64) string {
		if valor == math.Trunc(valor) && valor >= float64(min) && valor <= float64(max) { // NaN falha em tudo; ±Inf, no intervalo
			return ""
		}
		return mensagem
	}
}

// numero escreve um limite sem casas inúteis: 0 e 100, não 0.000000.
func numero(x float64) string { return strconv.FormatFloat(x, 'f', -1, 64) }
