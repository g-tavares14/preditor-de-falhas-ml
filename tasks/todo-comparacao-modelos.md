# Tarefas: Comparação árvore × Random Forest × XGBoost e exportação

Spec: `SPEC-comparacao-modelos.md`. Plano: `tasks/plan-comparacao-modelos.md`.
**Execução em lotes** (como no piso): o implementador faz todas as tarefas do lote em sequência e só para no
checkpoint. Lotes: **1 = M1 a M3**, **2 = M4 e M5**, **3 = M6 e M7**. Cada lote começa só depois do checkpoint anterior
ser aprovado pelo dono.

**Paradas obrigatórias** (parar na hora e relatar, sem afrouxar nada):
- `xgboost` não instala ou não importa (OpenMP, roda para a versão do Python);
- uma checagem existente falha, ou `arvore`/`ajuste`/`replay` mudam de saída;
- seria preciso mudar algo fora da lista de arquivos da tarefa (inclusive o Gold);
- o treino de uma grade passa de ~10 min (propor grade menor ao dono);
- o teste for lido ou medido.

Nada é commitado sem o dono pedir. Não mexer em `notebooks/02_post_medicoes_periodicas.ipynb` nem em
`.claude/agents/implementer.md`. Antes de mexer em código, copie `data/modelo/` para `data/modelo_antes_comparacao/` (M1).

## Fase 1: modelos

- [x] **M1: dependência e cópia de referência**
  - Descrição: copiar `data/modelo/` e `web/dados/replay.json` para `data/modelo_antes_comparacao/` e
    `data/replay_antes_comparacao.json`; `brew install libomp` (o dono liberou em 10/10/2026); `uv add xgboost`.
  - Aceite: `uv run python -c "import xgboost; print(xgboost.__version__)"` funciona; `import preditor.__main__` funciona;
    `diff -rq` entre as cópias e os originais é vazio; `git status` mostra só `pyproject.toml` e `uv.lock`.
  - Depende de: nada. Arquivos: `pyproject.toml`, `uv.lock`. Tamanho: S.

- [x] **M2: Random Forest**
  - Descrição: constantes em `config.py` (grade, `max_features`, nomes de arquivo, `MODELO_FLORESTA`), com origem;
    `modelo/floresta.py` com busca na grade (treino → validação), F1 de treino e de validação, nº de nós/árvores,
    tempo de treino, escolhida pela regra da Tarefa 4 e previsão em texto. Mesma estrutura de `ajuste.py`.
  - Aceite: a busca roda e devolve uma `escolhida`; mesma semente duas vezes dá as mesmas previsões; o X tem exatamente as
    10 colunas; `fit` só no treino; o F1 da escolhida é recalculado de forma independente e confere.
  - Verificação: script curto no scratchpad ou `uv run python -c` chamando `Floresta().buscar(dados)`; tempo anotado.
  - Depende de: M1. Arquivos: `config.py`, `modelo/floresta.py`. Tamanho: M.

- [x] **M3: XGBoost**
  - Descrição: igual a M2 para `modelo/boosting.py`; classes ↔ inteiros só dentro do modelo; `sample_weight` pelo mesmo
    dicionário de pesos; sem `early_stopping`.
  - Aceite: idem M2; as previsões voltam como `OK`/`RISCO`/`FALHA`; `NaN` aceito no X.
  - Depende de: M1. Arquivos: `config.py`, `modelo/boosting.py`. Tamanho: M.

### Checkpoint 1: fim do lote 1 (M1 a M3). O implementador para aqui.
- [x] Relatório: versões, tempo de treino de cada grade, escolhida de cada família e F1 da validação, desvios
- [ ] Revisão do agente principal e do dono antes do lote 2

## Fase 2: comparação

- [x] **M4: `comparacao.py`, `execucao_comparacao.py` e o comando `comparar`**
  - Descrição: mede as 5 linhas nas mesmas linhas da validação (reaproveita `Avaliacao`), grava `busca_floresta.csv`,
    `busca_boosting.csv`, `comparacao_modelos.csv`, `matriz_comparacao.csv`, `ic_pareado.csv`, `escolha.json`,
    `importancias.csv`; regra de escolha entre famílias; IC pareado por fluxo; todas as checagens da spec; liga o
    comando em `__main__.py` (fora da execução sem argumento).
  - Aceite: `uv run python -m preditor comparar` termina com todas as checagens; a escolha é recalculada de novo a partir
    de `comparacao_modelos.csv`; mesma execução duas vezes = mesmos arquivos; o teste fica fechado.
  - Depende de: M2, M3. Arquivos: `config.py`, `modelo/comparacao.py`, `modelo/execucao_comparacao.py`, `__main__.py`. Tamanho: L.

- [x] **M5: rodar, conferir identidade e anotar números**
  - Descrição: rodar `comparar`; rodar `arvore`, `ajuste` e `replay` e conferir que os arquivos são idênticos aos de
    `data/modelo_antes_comparacao/` e `data/replay_antes_comparacao.json`.
  - Aceite: `diff -rq` vazio (fora de `data/modelo/comparacao/`); tabela das 5 linhas com F1 macro, recall de FALHA, F1 por
    classe, OK → FALHA, tamanho, tempos e o IC pareado, no relatório do implementador.
  - Depende de: M4. Arquivos: nenhum. Tamanho: S.

### Checkpoint 2: fim do lote 2 (M4 e M5). O implementador para aqui.
- [x] `comparar` passa; `arvore`, `ajuste`, `replay` idênticos
- [x] Números e escolha da regra no relatório do implementador
- [ ] Revisão do agente principal e do dono antes do lote 3

## Fase 3: exportação e relatório

- [x] **M6: `exportacao.py` e o comando `exportar`**
  - Descrição: lê `escolha.json`, refaz o modelo escolhido e a árvore ajustada, grava `modelo_final.joblib`,
    `arvore_ajustada.joblib` (e o JSON nativo se for XGBoost), `LEIA-ME.md` (colunas, classes, versões, SHA-256, aviso do
    pickle) e `exemplo_de_uso.py`.
  - Aceite: em **processo novo**, o `.joblib` recarregado reproduz exatamente as previsões da validação; aceita `NaN`; só
    devolve `OK`/`RISCO`/`FALHA`; abre sem importar `preditor`; o `exemplo_de_uso.py` roda a partir de outra pasta.
  - Depende de: M5. Arquivos: `modelo/exportacao.py`, `__main__.py`, `config.py`. Tamanho: M.

- [x] **M7: relatório e documentos**
  - Descrição: `docs/relatorio_comparacao_modelos.md` (conteúdo da spec), `docs/README.md`, `AGENTS.md` (estágio,
    comandos, decisões, checagens), memória do projeto. Cada número vem de execução; ressalvas ditas.
  - Aceite: critérios de sucesso 1 a 6 da spec marcados; conferência dos números do texto contra os CSVs.
  - Depende de: M6. Arquivos: `docs/relatorio_comparacao_modelos.md`, `docs/README.md`, `AGENTS.md`, `SPEC-comparacao-modelos.md`. Tamanho: M.

### Checkpoint final: fim do lote 3 (M6 e M7)
- [x] Critérios de sucesso 1 a 6 marcados
- [ ] `.joblib` entregável conferido pelo dono; commit só se ele pedir
