// Package previsao junta as três coisas que uma previsão precisa: validar, perguntar ao modelo e guardar a resposta.
package previsao

import (
	"context"
	"time"

	"preditor/internal/banco"
	"preditor/internal/medicao"
	"preditor/internal/modelo"
)

// As origens possíveis de um pedido. `OrigemFormulario` é a tela Testar do site (o nome ficou da época em que era um formulário Razor,
// e as linhas antigas do histórico já usam este valor).
const (
	OrigemAPI        = "api"
	OrigemFormulario = "formulario"
)

// Servico é o único caminho que grava uma previsão: a API e a tela Testar passam por ele.
type Servico struct {
	Modelo *modelo.Cliente
	Banco  *banco.Banco
	// Agora existe para o teste fixar a hora; em produção é time.Now.
	Agora func() time.Time
}

// Prever devolve os erros de validação por coluna (e nenhuma previsão), ou a previsão já gravada.
// Modelo fora do ar = *modelo.IndisponivelErro, e nada é gravado.
func (s *Servico) Prever(ctx context.Context, m medicao.Medicao, origem string) (map[string][]string, *banco.Previsao, error) {
	if erros := medicao.Validar(m); len(erros) > 0 {
		return erros, nil, nil
	}

	resposta, err := s.Modelo.Prever(ctx, m)
	if err != nil {
		return nil, nil, err
	}

	// Só grava o que o modelo respondeu: serviço fora do ar nunca deixa uma linha no histórico.
	agora := s.Agora
	if agora == nil {
		agora = time.Now
	}
	p := &banco.Previsao{
		// O banco guarda 7 casas de fração (100 ns, o formato do EF Core): truncar aqui faz o POST e o GET mostrarem a mesma hora.
		CriadaEmUTC:  agora().UTC().Truncate(100 * time.Nanosecond),
		Entrada:      m,
		Classe:       resposta.Classe,
		ProbFalha:    resposta.Probabilidades["FALHA"],
		ProbOk:       resposta.Probabilidades["OK"],
		ProbRisco:    resposta.Probabilidades["RISCO"],
		ModeloSHA256: resposta.SHA256,
		Origem:       origem,
	}
	if err := s.Banco.Inserir(ctx, p); err != nil {
		return nil, nil, err
	}
	return nil, p, nil
}
