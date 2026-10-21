package medicao

import (
	"math"
	"slices"
	"sort"
	"testing"
)

func ptr(v float64) *float64 { return &v }

func chaves(erros map[string][]string) []string {
	var nomes []string
	for nome := range erros {
		nomes = append(nomes, nome)
	}
	sort.Strings(nomes)
	return nomes
}

func TestMedicaoToda_ausente_e_valida(t *testing.T) {
	if erros := Validar(Medicao{}); len(erros) != 0 {
		t.Fatalf("medição toda ausente devia ser válida, deu %v", erros)
	}
}

func TestMedicaoTipica_e_valida(t *testing.T) {
	m := Medicao{ptr(6), ptr(45), ptr(2), ptr(0), ptr(0), ptr(0), ptr(0), ptr(1), ptr(0.1), ptr(0.5)}
	if erros := Validar(m); len(erros) != 0 {
		t.Fatalf("medição típica devia ser válida, deu %v", erros)
	}
}

func TestPerda_fora_de_0_a_100_e_recusada(t *testing.T) {
	for _, perda := range []float64{-0.1, 100.1, math.NaN(), math.Inf(1)} {
		erros := Validar(Medicao{PerdaPct: ptr(perda)})
		if got := erros["perda_pct"]; !slices.Equal(got, []string{"Tem de estar entre 0 e 100."}) {
			t.Errorf("perda %v: esperava o erro de faixa, veio %v", perda, got)
		}
	}
}

func TestPerda_dentro_de_0_a_100_passa(t *testing.T) {
	for _, perda := range []float64{0, 100, 37.5} {
		if erros := Validar(Medicao{PerdaPct: ptr(perda)}); len(erros) != 0 {
			t.Errorf("perda %v devia passar, deu %v", perda, erros)
		}
	}
}

func TestTimeout_so_aceita_0_ou_1(t *testing.T) {
	for _, valor := range []float64{2, 0.5, -1, math.NaN()} {
		erros := Validar(Medicao{TimeoutAtual: ptr(valor)})
		if got := erros["timeout_atual"]; !slices.Equal(got, []string{"Tem de ser 0 ou 1."}) {
			t.Errorf("timeout %v: esperava o erro binário, veio %v", valor, got)
		}
	}
	for _, valor := range []float64{0, 1} {
		if erros := Validar(Medicao{TimeoutAtual: ptr(valor)}); len(erros) != 0 {
			t.Errorf("timeout %v devia passar, deu %v", valor, erros)
		}
	}
}

func TestContagem_da_janela_e_inteiro_de_0_a_5(t *testing.T) {
	for _, valor := range []float64{6, -1, 2.5, math.NaN()} {
		erros := Validar(Medicao{N5Timeout: ptr(valor), N5Aumento80: ptr(valor), N5Moderado: ptr(valor)})
		for _, coluna := range []string{"n5_timeout", "n5_aumento80", "n5_moderado"} {
			if got := erros[coluna]; !slices.Equal(got, []string{"Tem de ser um inteiro de 0 a 5."}) {
				t.Errorf("%s = %v: esperava o erro de inteiro, veio %v", coluna, valor, got)
			}
		}
	}
	for _, valor := range []float64{0, 5, 3} {
		if erros := Validar(Medicao{N5Timeout: ptr(valor)}); len(erros) != 0 {
			t.Errorf("n5_timeout %v devia passar, deu %v", valor, erros)
		}
	}
}

func TestMetrica_relativa_infinita_ou_NaN_e_recusada(t *testing.T) {
	for _, valor := range []float64{math.Inf(1), math.Inf(-1), math.NaN()} {
		erros := Validar(Medicao{ZRobusto: ptr(valor), Media5Z: ptr(valor)})
		for _, coluna := range []string{"z_robusto", "media5_z"} {
			if got := erros[coluna]; !slices.Equal(got, []string{"Tem de ser um número finito ou null."}) {
				t.Errorf("%s = %v: esperava o erro de número finito, veio %v", coluna, valor, got)
			}
		}
	}
	if erros := Validar(Medicao{ZRobusto: ptr(-1e9), AumentoPct: ptr(1e9)}); len(erros) != 0 {
		t.Errorf("números grandes mas finitos devem passar, deu %v", erros)
	}
}

func TestErros_de_varias_colunas_vem_juntos(t *testing.T) {
	erros := Validar(Medicao{PerdaPct: ptr(150), TimeoutAtual: ptr(3)})
	if got := chaves(erros); !slices.Equal(got, []string{"perda_pct", "timeout_atual"}) {
		t.Fatalf("esperava erros em perda_pct e timeout_atual, veio %v", got)
	}
}

func TestToda_coluna_tem_regra(t *testing.T) {
	// Se uma coluna nova entrar em `Colunas` sem regra, `regras[nome]` seria nil e a API cairia em pânico com o primeiro valor.
	for _, coluna := range (Medicao{}).Colunas() {
		if regras[coluna.Nome] == nil {
			t.Errorf("a coluna %q não tem regra", coluna.Nome)
		}
	}
}
