# Tarefas: Teste único da Tarefa 5

Spec: `SPEC-teste-final.md`. Plano: `tasks/plan-teste-final.md`.
**Execução em lotes:** **1 = T1 a T3**, **2 = T4**, depois a **abertura do teste (T5, pela sessão principal)** e o
**lote 3 = T6**. Cada lote só começa depois do checkpoint anterior ser aprovado pelo dono.

**REGRA DURA:** o implementador **nunca** roda `teste --abrir-o-teste`, nunca lê o bloco `teste` do Gold com `DadosTeste`
(só com `validacao`) e nunca cria `data/modelo/teste/TESTE_ABERTO.json`. A trava e a abertura são testadas só em pasta
temporária e com dados da validação. O teste só é aberto na T5, pela sessão principal, depois de o dono dizer "pode abrir".

**Paradas obrigatórias** (parar na hora e relatar, sem afrouxar nada):
- o ensaio não reproduz os números da validação (`comparacao_modelos.csv`);
- `arvore`, `ajuste`, `replay`, `comparar` ou `exportar` mudam de saída;
- seria preciso mudar algo fora da lista de arquivos da tarefa;
- qualquer necessidade de ler o bloco de teste antes da T5.

Nada é commitado sem o dono pedir. Não mexer em `notebooks/02_post_medicoes_periodicas.ipynb` nem em
`.claude/agents/implementer.md`. Antes de mexer em código, copiar `data/modelo/` (inclusive `comparacao/` e
`exportado/`) para `data/modelo_antes_teste/` e `web/dados/replay.json` para `data/replay_antes_teste.json`.

## Fase 1: código comum e ensaio

- [x] **T1: leitura por bloco e parâmetro de liberação**
  - Descrição: cópia de referência; constantes em `config.py` (caminhos de `data/modelo/teste/`, nomes de arquivo, IC);
    `Avaliacao.medir` ganha um parâmetro explícito que libera o bloco `teste` (padrão: recusa); `modelo/dados_teste.py` com
    `DadosTeste(bloco)`: lê o parquet, aplica a regra de linhas da spec (bloco, `status_futuro` não nulo; folga só no
    treino/validação, igual ao `DadosModelo`) e entrega X de 10 colunas, y, `status_atual` e localização.
  - Aceite: com `bloco="validacao"`, `DadosTeste` entrega as mesmas linhas, X e y que `DadosModelo` na validação
    (conferido por igualdade exata); com `bloco="teste"` só se **instancia** em modo "contar" (devolve o N, que bate com
    `DadosModelo.n_teste`), sem entregar linhas nem rodar medição; `Avaliacao.medir` recusa o teste sem o parâmetro.
  - Verificação: script no scratchpad; `arvore` e `ajuste` com saída idêntica.
  - Depende de: nada. Arquivos: `config.py`, `modelo/avaliacao.py`, `modelo/dados_teste.py`. Tamanho: M.

- [x] **T2: medição comum, modo `--ensaio` e o comando `teste`**
  - Descrição: `modelo/execucao_teste.py` carrega o `.joblib` (SHA-256 conferido), prevê, mede modelo e persistência
    (mesmas funções da validação), calcula acerto por transição, IC 95 % por fluxo do ganho sobre a persistência, escolhe os
    dois casos concretos (`CASOS_ERRO`, conferidos por laço), aplica a regra preditor/detector, confere a contagem de
    fluxos sem baseline ("fluxo não visto") e imprime tudo. Modo `--ensaio` roda isso na validação, confere contra
    `comparacao_modelos.csv` e grava `ensaio_ok.json`. Liga o comando em `__main__.py` (`teste`, `--ensaio`,
    `--abrir-o-teste`); neste lote `--abrir-o-teste` só explica e sai (a abertura vem na T4).
  - Aceite: `uv run python -m preditor teste --ensaio` termina com todas as checagens, reproduz F1 macro 0,6977, a matriz e
    o recall de FALHA 0,505 da floresta e a persistência; o IC e os dois casos saem (na validação, rotulados "ensaio");
    nenhum `fit`; só `execucao_teste.py` importa `dados_teste` (`grep`).
  - Depende de: T1. Arquivos: `modelo/execucao_teste.py`, `__main__.py`, `config.py`. Tamanho: L.

- [x] **T3: rodar o ensaio e conferir identidade**
  - Descrição: rodar o ensaio duas vezes (mesmo resultado); rodar `arvore`, `ajuste`, `replay`, `comparar` e `exportar` e
    comparar com `data/modelo_antes_teste/` e `data/replay_antes_teste.json`.
  - Aceite: `diff -rq` vazio (fora de `data/modelo/teste/`); relatório com os números do ensaio ao lado dos da validação.
  - Depende de: T2. Arquivos: nenhum. Tamanho: S.

### Checkpoint 1: fim do lote 1 (T1 a T3). O implementador para aqui.
- [ ] O ensaio reproduz a validação; os outros comandos idênticos
- [ ] Nenhuma linha do bloco de teste lida (só o N)
- [ ] Revisão do agente principal e do dono antes do lote 2

## Fase 2: trava e abertura (sem abrir)

- [x] **T4: trava, carimbo e abertura implementados e testados SEM abrir o teste**
  - Descrição: `--abrir-o-teste` exige o carimbo `ensaio_ok.json` válido (hash do modelo), grava `TESTE_ABERTO.json`
    (`em_andamento`, depois `concluido`), recusa se o arquivo existe, lê o bloco de teste com `DadosTeste("teste")`, confere
    N = `n_teste`, mede, grava as saídas e verifica. A função da trava recebe o caminho como argumento.
  - Aceite (tudo em pasta temporária, com dados da validação no lugar do teste, **sem tocar `data/modelo/teste/`**):
    a trava cria o arquivo e recusa a segunda chamada; o comando recusa sem o carimbo e com o hash trocado; recusa sem
    `--abrir-o-teste`; a gravação das saídas funciona; `grep` mostra que ninguém mais importa `dados_teste`.
  - Verificação: script no scratchpad com pasta temporária; `diff` dos outros comandos contra a referência.
  - Depende de: T3. Arquivos: `modelo/execucao_teste.py`, `config.py`. Tamanho: M.

### Checkpoint 2: fim do lote 2 (T4). O implementador para aqui.
- [x] Trava, carimbo e recusas testados fora de `data/modelo/teste/`
- [x] `data/modelo/teste/` sem `TESTE_ABERTO.json`
- [ ] **O dono diz "pode abrir o teste"** (só então a sessão principal faz a T5)

## Fase 3: abertura e documentos

- [x] **T5: abrir o teste (sessão principal, não o implementador)** — feita pela sessão principal em 10/10/2026, às 14:49
  (`aberto_em` 14:49:21, `concluido_em` 14:49:23, -03; `TESTE_ABERTO.json` em `concluido`; segunda tentativa recusada, relatado pela sessão principal).
  - Descrição: `uv run python -m preditor teste --abrir-o-teste`, uma vez. Conferir as checagens, anotar o resultado, a
    declaração preditor/detector e a hora.
  - Aceite: todas as checagens passam; a segunda tentativa é recusada; `TESTE_ABERTO.json` em `concluido`.
  - Depende de: Checkpoint 2 aprovado. Arquivos: nenhum. Tamanho: S.

- [x] **T6: relatório, ficha e documentos** — feito em 10/10/2026 (`docs/resultado_teste_final.md`, `docs/ficha_modelo_final.md`, `AGENTS.md`, `docs/README.md`, `SPEC-teste-final.md`, guia e relatório de comparação, memória).
  - Descrição: `docs/resultado_teste_final.md` (estilo dos outros; números de `data/modelo/teste/`), `docs/ficha_modelo_final.md`
    (seção 5 do diário), `AGENTS.md`, `docs/README.md`, `SPEC-teste-final.md` (critérios) e a memória do projeto. Confirmar com
    o dono o dicionário v0.4 (pergunta 3 da spec).
  - Aceite: critérios de sucesso 1 a 7 marcados; todo número vindo de execução; limitação do fluxo novo declarada.
  - Depende de: T5. Arquivos: `docs/resultado_teste_final.md`, `docs/ficha_modelo_final.md`, `AGENTS.md`, `docs/README.md`. Tamanho: M.

### Checkpoint final
- [x] Critérios de sucesso 1 a 7 marcados (com evidência na SPEC, seção "Critérios de sucesso")
- [ ] O dono leva o resultado ao diário da Tarefa 5; commit só se ele pedir
