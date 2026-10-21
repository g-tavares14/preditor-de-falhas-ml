package api_test

import (
	"net/http"
	"testing"
)

// O banco guarda a hora com 7 casas de fração (100 ns). Se o POST devolvesse mais casas que isso, o mesmo registro apareceria com
// horas diferentes no POST e no GET do histórico.
func TestHoraDoPost_eAMesmaDoHistorico(t *testing.T) {
	a := novoAmbiente(t, novoModeloFalso(t).URL)

	criada := lerJSON(t, a.postar(t, `{"z_robusto":1}`))["criadaEmUtc"]
	itens := lerJSON(t, a.pedir(t, http.MethodGet, "/api/previsoes", "", nil))["itens"].([]any)
	listada := itens[0].(map[string]any)["previsao"].(map[string]any)["criadaEmUtc"]

	if criada != listada {
		t.Errorf("hora do POST %v ≠ hora do histórico %v", criada, listada)
	}
}
