package banco

import (
	"path/filepath"
	"testing"
	"time"

	"preditor/internal/medicao"
)

func abrirTemporario(t *testing.T) *Banco {
	t.Helper()
	b, err := Abrir(filepath.Join(t.TempDir(), "pasta-nova", "t.db")) // a pasta ainda não existe: Abrir a cria
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { b.Fechar() })
	return b
}

func f(v float64) *float64 { return &v }

func TestInserirEListar_preservaAusentesEValores(t *testing.T) {
	b := abrirTemporario(t)
	quando := time.Date(2026, 10, 20, 12, 30, 45, 123456700, time.UTC)
	p := &Previsao{
		CriadaEmUTC: quando, Classe: "FALHA", ProbFalha: 0.8, ProbOk: 0.1, ProbRisco: 0.1, ModeloSHA256: "abc", Origem: "api",
		Entrada: medicao.Medicao{ZRobusto: f(6), PerdaPct: f(0), N5Timeout: f(2)},
	}
	if err := b.Inserir(t.Context(), p); err != nil {
		t.Fatal(err)
	}
	if p.ID == 0 {
		t.Error("Inserir devia preencher o ID")
	}

	itens, total, err := b.Listar(t.Context(), 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if total != 1 || len(itens) != 1 {
		t.Fatalf("total=%d itens=%d", total, len(itens))
	}
	lido := itens[0]
	if !lido.CriadaEmUTC.Equal(quando) {
		t.Errorf("a data mudou na ida e volta: %v → %v", quando, lido.CriadaEmUTC)
	}
	if lido.Entrada.ZRobusto == nil || *lido.Entrada.ZRobusto != 6 {
		t.Errorf("z_robusto: %v", lido.Entrada.ZRobusto)
	}
	// Zero e ausente são coisas diferentes: perda 0 % é uma medição, sem perda_pct é "não sei".
	if lido.Entrada.PerdaPct == nil || *lido.Entrada.PerdaPct != 0 {
		t.Errorf("perda_pct 0 tem de voltar como 0, não como ausente: %v", lido.Entrada.PerdaPct)
	}
	if lido.Entrada.AumentoPct != nil {
		t.Errorf("aumento_pct ausente tem de voltar nil: %v", *lido.Entrada.AumentoPct)
	}
	if lido.Classe != "FALHA" || lido.ProbFalha != 0.8 || lido.ModeloSHA256 != "abc" || lido.Origem != "api" {
		t.Errorf("campos de saída: %+v", lido)
	}
}

func TestListar_ordemEPaginas(t *testing.T) {
	b := abrirTemporario(t)
	base := time.Date(2026, 10, 20, 12, 0, 0, 0, time.UTC)
	// Duas linhas no MESMO instante: o desempate é o Id (a inserida depois vem primeiro).
	for i, quando := range []time.Time{base, base.Add(time.Minute), base.Add(time.Minute), base.Add(2 * time.Minute)} {
		p := &Previsao{CriadaEmUTC: quando, Classe: "OK", ModeloSHA256: "x", Origem: "api", Entrada: medicao.Medicao{ZRobusto: f(float64(i))}}
		if err := b.Inserir(t.Context(), p); err != nil {
			t.Fatal(err)
		}
	}

	itens, total, err := b.Listar(t.Context(), 1, 3)
	if err != nil {
		t.Fatal(err)
	}
	if total != 4 {
		t.Fatalf("total %d", total)
	}
	var zs []float64
	for _, it := range itens {
		zs = append(zs, *it.Entrada.ZRobusto)
	}
	if len(zs) != 3 || zs[0] != 3 || zs[1] != 2 || zs[2] != 1 {
		t.Errorf("página 1 (z, da mais nova para a mais antiga): %v, esperava [3 2 1]", zs)
	}
	resto, _, _ := b.Listar(t.Context(), 2, 3)
	if len(resto) != 1 || *resto[0].Entrada.ZRobusto != 0 {
		t.Errorf("página 2 devia ter só a mais antiga (z=0): %+v", resto)
	}
	vazia, _, _ := b.Listar(t.Context(), 9, 3)
	if vazia == nil || len(vazia) != 0 {
		t.Errorf("página depois do fim = lista vazia e não nil: %#v", vazia)
	}
}

func TestListar_leLinhasNoFormatoDoEFCore(t *testing.T) {
	// O volume da produção tem linhas gravadas pela API em C# (EF Core): a data é TEXT "yyyy-MM-dd HH:mm:ss.FFFFFFF", com zeros à direita
	// cortados e sem a fração quando ela é zero. As duas formas têm de ler, e as linhas antigas e as novas se ordenam juntas.
	b := abrirTemporario(t)
	for _, quando := range []string{"2026-10-16 09:08:56.1234567", "2026-10-16 09:08:57", "2026-10-16 09:08:57.5"} {
		_, err := b.db.Exec(`INSERT INTO "Previsoes" ("CriadaEmUtc","Classe","ProbFalha","ProbOk","ProbRisco","ModeloSha256","Origem") VALUES (?, 'OK', 0.1, 0.8, 0.1, 'ef', 'formulario')`, quando)
		if err != nil {
			t.Fatal(err)
		}
	}
	novo := &Previsao{CriadaEmUTC: time.Date(2026, 10, 16, 9, 8, 57, 250_000_000, time.UTC), Classe: "OK", ModeloSHA256: "go", Origem: "api"}
	if err := b.Inserir(t.Context(), novo); err != nil {
		t.Fatal(err)
	}

	itens, _, err := b.Listar(t.Context(), 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	var segundos []string
	for _, it := range itens {
		segundos = append(segundos, it.CriadaEmUTC.Format("05.9999999"))
	}
	esperado := []string{"57.5", "57.25", "57", "56.1234567"}
	if len(segundos) != 4 {
		t.Fatalf("esperava 4 linhas, vieram %d", len(segundos))
	}
	for i := range esperado {
		if segundos[i] != esperado[i] {
			t.Fatalf("ordem das datas: %v, esperava %v", segundos, esperado)
		}
	}
}

func TestAbrir_duasVezesNoMesmoArquivoNaoApagaOHistorico(t *testing.T) {
	arquivo := filepath.Join(t.TempDir(), "t.db")
	b, err := Abrir(arquivo)
	if err != nil {
		t.Fatal(err)
	}
	if err := b.Inserir(t.Context(), &Previsao{CriadaEmUTC: time.Now(), Classe: "OK", ModeloSHA256: "x", Origem: "api"}); err != nil {
		t.Fatal(err)
	}
	b.Fechar()

	b, err = Abrir(arquivo) // a partida seguinte do contêiner
	if err != nil {
		t.Fatal(err)
	}
	defer b.Fechar()
	if _, total, _ := b.Listar(t.Context(), 1, 1); total != 1 {
		t.Errorf("o histórico devia sobreviver a uma nova abertura, total=%d", total)
	}
}
