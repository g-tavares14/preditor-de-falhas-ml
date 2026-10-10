# Plano: Teste único da Tarefa 5

Spec: `SPEC-teste-final.md` (aprovada pelo dono em 10/10/2026). Tarefas: `tasks/todo-teste-final.md`.

## Resumo

Um comando `teste` com dois modos que usam **o mesmo caminho de código**: `--ensaio` (linhas da validação, prova que o
código reproduz os números já medidos da floresta) e `--abrir-o-teste` (linhas do bloco de teste, uma vez só, com trava).
O código se constrói e se verifica **inteiro no ensaio**; o teste só é aberto depois de o dono autorizar, e quem abre é a
sessão principal, nunca o implementador. Depois da abertura, os números vão para o relatório e para a ficha.

## Decisões de arquitetura

- **Um caminho de código, dois blocos.** `DadosTeste` (em `modelo/dados_teste.py`) recebe o nome do bloco: `validacao` no
  ensaio, `teste` na abertura. Assim o ensaio é um teste de verdade do código de leitura, X e medição, sem tocar o teste.
  Só `execucao_teste.py` importa `dados_teste` (checado por `grep`); `DadosModelo` não muda e continua sem guardar o teste.
- **O modelo é o arquivo.** A medição carrega `data/modelo/exportado/modelo_final.joblib` e confere o SHA-256 com o do
  `LEIA-ME.md`/`escolha.json`. Não se refaz nem se retreina nada (o comando não chama `fit`).
- **`Avaliacao.medir` ganha um parâmetro explícito** para liberar o bloco `teste`; o padrão continua recusando. Os outros
  comandos não passam o parâmetro, então as saídas deles não mudam (prova: `diff` contra as cópias de referência).
- **Trava em arquivo.** `TESTE_ABERTO.json` é gravado antes de ler o teste (`em_andamento`) e atualizado no fim
  (`concluido`); a existência dele recusa uma segunda abertura. A função da trava recebe o caminho como argumento, para o
  implementador testá-la numa pasta temporária sem tocar `data/modelo/teste/`.
- **Carimbo do ensaio.** O ensaio gravando `ensaio_ok.json` (hash do modelo e do código de medição) é condição para a
  abertura; o carimbo é recusado se o `.joblib` mudou depois.
- **IC e casos reutilizam o que já existe:** bootstrap por fluxo do `comparacao.ic_pareado`; escolha dos casos por
  `Avaliacao._escolher` com `CASOS_ERRO` (já adaptados às 10 colunas, se for preciso), com a conferência por laço.
- **Documentos só depois dos números.** `docs/resultado_teste_final.md` e `docs/ficha_modelo_final.md` só são escritos
  depois da abertura, com os números de `data/modelo/teste/`.

## Grafo de dependências

```
T1 parâmetro de Avaliacao + DadosTeste (bloco como argumento) + config
 └─ T2 medição comum (modelo, persistência, IC, casos, declaração) + modo --ensaio + comando
     └─ T3 rodar o ensaio, reproduzir a validação e conferir identidade dos outros comandos   ── Checkpoint 1
         └─ T4 trava, carimbo do ensaio, abertura (--abrir-o-teste), gravação; testadas SEM abrir o teste  ── Checkpoint 2
             └─ (decisão do dono: "pode abrir o teste")
                 └─ T5 abrir o teste (sessão principal) e conferir
                     └─ T6 relatório + ficha + AGENTS.md + docs/README + memória
```

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| O teste é lido durante o desenvolvimento | Alto | `DadosTeste` recebe o bloco por argumento; até T5 só roda com `validacao`; o implementador não roda `--abrir-o-teste` (regra no todo); a trava é testada em pasta temporária |
| O ensaio não bate com a validação | Médio | É o objetivo do ensaio: se não bater, para-se e relata-se, sem seguir para o teste |
| Mexer em `Avaliacao` muda outras saídas | Alto | Só se acrescenta um parâmetro com padrão; `diff` das saídas de `arvore`, `ajuste`, `replay`, `comparar` e `exportar` em T3 e T4 |
| `CASOS_ERRO`/`_escolher` assumem as 8 colunas (`COLUNAS_ARVORE`) | Médio | O implementador lê `avaliacao.py`; se for preciso adaptar, só por parâmetro, sem alterar o `arvore` e o `ajuste` |
| Falha no meio da abertura | Alto | O estado `em_andamento` já bloqueia; o dono decide e registra |
| Resultado ruim no teste leva a querer reajustar | Alto | Regra da spec: nada é reajustado; o relatório declara como é |
| O dicionário v0.4 não existir no repositório | Baixo | A ficha traz o dicionário das 10 colunas e marca que é o do grupo; pergunta ao dono em T6 |

## Verificação

Sem framework de testes; cada tarefa termina rodando o comando afetado, que para com `assert`.

- **T1/T2:** o ensaio roda de ponta a ponta na validação.
- **T3:** o ensaio reproduz `comparacao_modelos.csv` (F1 macro, recalls, matriz) e `arvore`/`ajuste`/`replay`/`comparar`/`exportar` seguem idênticos.
- **T4:** trava, carimbo e recusa da 2ª abertura testados em pasta temporária; `--abrir-o-teste` sem o ensaio é recusado.
- **T5:** todas as checagens da abertura passam; a segunda tentativa é recusada.
- **T6:** critérios de sucesso 1 a 7 da spec marcados.

## Skills do catálogo

Nenhuma é necessária.
