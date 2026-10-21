package medicao

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestDecodificar_aceita_colunas_ausentes_e_nulas(t *testing.T) {
	m, err := Decodificar([]byte(`{"z_robusto": 6.0, "aumento_pct": null, "n5_moderado": 1}`))
	if err != nil {
		t.Fatal(err)
	}
	if m.ZRobusto == nil || *m.ZRobusto != 6 || m.N5Moderado == nil || *m.N5Moderado != 1 {
		t.Errorf("valores presentes se perderam: %+v", m)
	}
	if m.AumentoPct != nil || m.PerdaPct != nil {
		t.Errorf("null e ausente têm de ficar ausentes (nil), não zero: %+v", m)
	}
}

func TestDecodificar_recusa_corpo_torto(t *testing.T) {
	casos := map[string]string{
		"coluna que o modelo não usa": `{"rtt":10.0}`,
		"texto no lugar de número":    `{"z_robusto":"3"}`,
		"NaN não é JSON":              `{"z_robusto":NaN}`,
		"não é JSON":                  `{nao e json`,
		"corpo vazio":                 ``,
		"null sozinho":                `null`,
		"lista":                       `[1,2]`,
		"dois objetos":                `{} {}`,
		"lixo depois do objeto":       `{} lixo`,
		"número fora do alcance":      `{"z_robusto":1e999}`,
	}
	for nome, corpo := range casos {
		t.Run(nome, func(t *testing.T) {
			_, err := Decodificar([]byte(corpo))
			if _, ok := err.(*FormatoInvalidoErro); !ok {
				t.Fatalf("esperava *FormatoInvalidoErro, veio %T (%v)", err, err)
			}
			if strings.Contains(err.Error(), "Go struct") || strings.Contains(err.Error(), "float64") {
				t.Errorf("a mensagem vaza o tipo do Go: %q", err.Error())
			}
		})
	}
}

func TestDecodificar_citar_a_coluna_do_tipo_errado(t *testing.T) {
	_, err := Decodificar([]byte(`{"perda_pct":"alta"}`))
	if err == nil || !strings.Contains(err.Error(), "perda_pct") {
		t.Fatalf("a mensagem devia citar a coluna, veio %v", err)
	}
}

func TestMedicao_serializa_as_10_chaves_com_null_explicito(t *testing.T) {
	// É isto que o Python recebe: ausente tem de ir como `null`, e não sumir (omitempty) nem virar 0.
	corpo, err := json.Marshal(Medicao{})
	if err != nil {
		t.Fatal(err)
	}
	var campos map[string]any
	if err := json.Unmarshal(corpo, &campos); err != nil {
		t.Fatal(err)
	}
	if len(campos) != 10 {
		t.Fatalf("esperava as 10 chaves, vieram %d: %s", len(campos), corpo)
	}
	for nome, valor := range campos {
		if valor != nil {
			t.Errorf("%s devia ser null, veio %v", nome, valor)
		}
	}
}
