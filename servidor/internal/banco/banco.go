// Package banco guarda as previsões num arquivo SQLite.
//
// A tabela `Previsoes` tem os mesmos nomes de coluna, tipos e índice que a migração `Inicial` do EF Core criava quando a API era em C#,
// e as datas seguem o formato do EF (`yyyy-MM-dd HH:mm:ss.FFFFFFF`, UTC). Assim o volume da produção, com o histórico dentro, abre sem
// migrar nada. A tabela `__EFMigrationsHistory` que o EF deixou no arquivo é ignorada.
package banco

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite" // o driver Go puro (sem CGO): a imagem ARM monta no Mac

	"preditor/internal/medicao"
)

// formatoDaData é o do EF Core no SQLite. O `.9999999` do Go corta zeros à direita e some se a fração for zero, como o `FFFFFFF` do .NET;
// por isso a ordem do texto é a ordem do tempo, e linhas antigas e novas se ordenam juntas.
const formatoDaData = "2006-01-02 15:04:05.9999999"

const esquema = `
CREATE TABLE IF NOT EXISTS "Previsoes" (
    "Id" INTEGER NOT NULL CONSTRAINT "PK_Previsoes" PRIMARY KEY AUTOINCREMENT,
    "CriadaEmUtc" TEXT NOT NULL,
    "ZRobusto" REAL NULL,
    "AumentoPct" REAL NULL,
    "JitterRelativo" REAL NULL,
    "PerdaPct" REAL NULL,
    "TimeoutAtual" REAL NULL,
    "N5Timeout" REAL NULL,
    "N5Aumento80" REAL NULL,
    "N5Moderado" REAL NULL,
    "Min5Z" REAL NULL,
    "Media5Z" REAL NULL,
    "Classe" TEXT NOT NULL,
    "ProbFalha" REAL NOT NULL,
    "ProbOk" REAL NOT NULL,
    "ProbRisco" REAL NOT NULL,
    "ModeloSha256" TEXT NOT NULL,
    "Origem" TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS "IX_Previsoes_CriadaEmUtc" ON "Previsoes" ("CriadaEmUtc");
`

// Previsao é uma linha da tabela: o que entrou, o que o modelo respondeu e qual modelo respondeu.
type Previsao struct {
	ID          int64
	CriadaEmUTC time.Time
	Entrada     medicao.Medicao
	Classe      string
	ProbFalha   float64
	ProbOk      float64
	ProbRisco   float64
	// ModeloSHA256 prova qual `.joblib` deu a classe.
	ModeloSHA256 string
	// Origem diz de onde veio o pedido: "api" (POST direto) ou "formulario" (a tela Testar do site).
	Origem string
}

type Banco struct{ db *sql.DB }

// Abrir cria a pasta e o arquivo se faltarem, liga o modo WAL e cria a tabela se ela ainda não existir.
func Abrir(arquivo string) (*Banco, error) {
	if pasta := filepath.Dir(arquivo); pasta != "." {
		if err := os.MkdirAll(pasta, 0o755); err != nil {
			return nil, fmt.Errorf("criar a pasta do banco: %w", err)
		}
	}
	// `busy_timeout` faz uma escrita esperar a outra em vez de falhar na hora; WAL deixa a leitura andar durante a escrita.
	dsn := "file:" + arquivo + "?_pragma=busy_timeout(5000)&_pragma=journal_mode(WAL)&_pragma=foreign_keys(1)"
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	// Uma conexão só: é uma API pequena, e assim nunca há duas escritas disputando o arquivo.
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(esquema); err != nil {
		db.Close()
		return nil, fmt.Errorf("criar a tabela: %w", err)
	}
	return &Banco{db: db}, nil
}

func (b *Banco) Fechar() error { return b.db.Close() }

// Inserir grava a previsão e preenche o ID.
func (b *Banco) Inserir(ctx context.Context, p *Previsao) error {
	e := p.Entrada
	resultado, err := b.db.ExecContext(ctx, `
INSERT INTO "Previsoes" ("CriadaEmUtc", "ZRobusto", "AumentoPct", "JitterRelativo", "PerdaPct", "TimeoutAtual",
    "N5Timeout", "N5Aumento80", "N5Moderado", "Min5Z", "Media5Z", "Classe", "ProbFalha", "ProbOk", "ProbRisco", "ModeloSha256", "Origem")
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		p.CriadaEmUTC.UTC().Format(formatoDaData),
		e.ZRobusto, e.AumentoPct, e.JitterRelativo, e.PerdaPct, e.TimeoutAtual, e.N5Timeout, e.N5Aumento80, e.N5Moderado, e.Min5Z, e.Media5Z,
		p.Classe, p.ProbFalha, p.ProbOk, p.ProbRisco, p.ModeloSHA256, p.Origem)
	if err != nil {
		return err
	}
	p.ID, err = resultado.LastInsertId()
	return err
}

// Listar devolve uma página do histórico, da previsão mais nova para a mais antiga, e o total de linhas.
// `pagina` começa em 1; quem chama já validou `pagina` e `tamanho`.
func (b *Banco) Listar(ctx context.Context, pagina, tamanho int) ([]Previsao, int, error) {
	var total int
	if err := b.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM "Previsoes"`).Scan(&total); err != nil {
		return nil, 0, err
	}

	linhas, err := b.db.QueryContext(ctx, `
SELECT "Id", "CriadaEmUtc", "ZRobusto", "AumentoPct", "JitterRelativo", "PerdaPct", "TimeoutAtual",
    "N5Timeout", "N5Aumento80", "N5Moderado", "Min5Z", "Media5Z", "Classe", "ProbFalha", "ProbOk", "ProbRisco", "ModeloSha256", "Origem"
FROM "Previsoes" ORDER BY "CriadaEmUtc" DESC, "Id" DESC LIMIT ? OFFSET ?`, tamanho, (pagina-1)*tamanho)
	if err != nil {
		return nil, 0, err
	}
	defer linhas.Close()

	itens := []Previsao{} // vazio e não nil: o JSON da API tem de dizer `[]`
	for linhas.Next() {
		var p Previsao
		var quando string
		e := &p.Entrada
		// `sql.Null[float64]` seria mais longo; o driver entrega REAL nulo como nil quando o destino é `**float64`.
		if err := linhas.Scan(&p.ID, &quando, &e.ZRobusto, &e.AumentoPct, &e.JitterRelativo, &e.PerdaPct, &e.TimeoutAtual,
			&e.N5Timeout, &e.N5Aumento80, &e.N5Moderado, &e.Min5Z, &e.Media5Z,
			&p.Classe, &p.ProbFalha, &p.ProbOk, &p.ProbRisco, &p.ModeloSHA256, &p.Origem); err != nil {
			return nil, 0, err
		}
		if p.CriadaEmUTC, err = time.ParseInLocation(formatoDaData, quando, time.UTC); err != nil {
			return nil, 0, fmt.Errorf("data %q da previsão %d: %w", quando, p.ID, err)
		}
		itens = append(itens, p)
	}
	return itens, total, linhas.Err()
}
