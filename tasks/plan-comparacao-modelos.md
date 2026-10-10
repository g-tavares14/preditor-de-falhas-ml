# Plano: Comparação árvore × Random Forest × XGBoost e exportação

Spec: `SPEC-comparacao-modelos.md` (aprovada pelo dono em 10/10/2026). Tarefas: `tasks/todo-comparacao-modelos.md`.

## Resumo

Dois modelos novos (`floresta.py`, `boosting.py`) seguem o desenho da árvore ajustada: grade pequena, treino só no treino,
medida na validação, escolha pela regra da Tarefa 4. Um comando `comparar` mede as cinco linhas (persistência, Tarefa 3,
ajustada, RF, XGBoost) nas **mesmas** linhas da validação, aplica a regra entre famílias e grava tudo em
`data/modelo/comparacao/`. Um comando `exportar` refaz o escolhido, verifica a recarga em processo novo e grava o
`.joblib`. O relatório vem por último. `arvore`, `ajuste`, `replay` e o Gold não mudam.

## Decisões de arquitetura

- **Reutilização, não alteração.** `DadosModelo` (`x_ajustado`, `y`, `status_atual_validacao`), `Avaliacao` e a regra de
  escolha de `ArvoreAjustada` ficam como estão. A regra "a até 0,005 do melhor, vence a mais simples" vale também entre
  famílias; se for preciso tirá-la de `ajuste.py` para um lugar comum, a saída do `ajuste` tem de continuar byte a byte igual.
- **Grades propostas** (o implementador confere o tempo de treino e registra a origem de cada número em `config.py`):
  - Random Forest: `n_estimators` {100, 300} × `max_depth` {4, 6, 8, 12} × `min_samples_leaf` {20, 50, 100, 200},
    `max_features="sqrt"`, Gini, `class_weight` = o da ajustada, `n_jobs=1` para reprodutibilidade simples → 32.
  - XGBoost: `n_estimators` {100, 300} × `learning_rate` {0,05; 0,1} × `max_depth` {2, 3, 4, 6}, `tree_method="hist"`,
    `sample_weight` pelo mesmo dicionário de pesos, sem parada antecipada → 16. Classes codificadas OK=0, RISCO=1,
    FALHA=2 só dentro do modelo; o resultado volta como texto.
  - Ordem de simplicidade do desempate: menos árvores, depois menor profundidade, depois folha mínima maior (RF) /
    `learning_rate` maior (XGBoost).
- **Semente 16** em tudo (`random_state`/`seed`). A checagem "mesma semente = mesmas previsões" roda os dois modelos duas vezes.
- **O X é o da ajustada** (10 colunas, `x_ajustado`). `NaN` fica `NaN`.
- **IC pareado** (bootstrap por fluxo, 2.000, semente 16): módulo próprio em `comparacao.py`, com a mesma reamostragem
  nas duas séries comparadas. Gravado em `ic_pareado.csv`; não decide a escolha.
- **Exportação sem o pacote `preditor`.** O arquivo é um `dict` (`modelo`, `colunas`, `classes`, `semente`, `versoes`,
  `parametros`) só com objetos de scikit-learn, XGBoost e biblioteca padrão. Para o XGBoost, `classes` mapeia 0/1/2 → texto.
  A árvore ajustada é exportada igual, em arquivo à parte. `LEIA-ME.md` traz SHA-256, versões e o aviso do pickle.
- **Fora do git:** todas as saídas ficam em `data/` (ignorada). O código, o relatório e o plano são versionados.

## Grafo de dependências

```
M1 dependência (libomp + xgboost) ── verifica import e que os comandos de hoje seguem iguais
 ├─ M2 Random Forest (config + floresta.py)
 └─ M3 XGBoost (config + boosting.py)
     └─ M4 comparação + comando `comparar` (regra de escolha, IC pareado, checagens)
         └─ M5 rodar `comparar`, conferir identidade de arvore/ajuste/replay, anotar números
             └─ M6 exportação + comando `exportar` (recarga em processo novo)
                 └─ M7 relatório + AGENTS.md + docs/README + memória
```

M2 e M3 são independentes, mas o mesmo implementador as faz em sequência.

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Sem roda do XGBoost para Python 3.14 / macOS, ou OpenMP ausente | Alto | M1 é a primeira tarefa e para o lote se `import xgboost` falhar; o dono decide (ex.: outro Python, ou `HistGradientBoostingClassifier` no lugar) |
| Treino da grade lento | Médio | Medir o tempo da primeira combinação em M2/M3; se passar de poucos minutos por modelo, reduzir a grade e registrar |
| Mexer em `ajuste.py` para reaproveitar a regra muda a saída do `ajuste` | Alto | Preferir copiar a regra por composição; se mexer, comparar `data/modelo/*.csv` e `*.json` antes e depois (cópia em `data/modelo_antes_comparacao/`) |
| Modelo grande no `.joblib` (300 árvores) | Baixo | Registrar o tamanho no `LEIA-ME.md`; a grade já limita |
| Versão do scikit-learn/XGBoost da professora diferente | Médio | Versões nos metadados e no `LEIA-ME.md`; para o XGBoost, exportar também o JSON nativo |
| O teste ser tocado por engano | Alto | Mesmas travas de hoje (`DadosModelo` não guarda o teste, `Avaliacao.medir` o recusa); o `comparar` imprime que o teste ficou fechado |
| Validação reaproveitada para escolher e comparar | Médio | Dito no relatório; IC pareado gravado; regra fixada antes |

## Verificação

Sem framework de testes: cada tarefa termina rodando o comando afetado, que para com `assert`.

- **Depois de M1:** `uv run python -c "import xgboost, preditor.__main__"` e `arvore` seguem funcionando.
- **Depois de M5 (checkpoint 2):** `comparar` passa; `arvore`, `ajuste`, `replay` regravam arquivos idênticos aos de antes.
- **Depois de M6:** a recarga em processo novo reproduz as previsões.
- **Depois de M7:** os 6 critérios de sucesso da spec marcados.

## Skills do catálogo

Nenhuma é necessária.
