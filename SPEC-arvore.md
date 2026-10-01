# Spec: Árvore inicial (Tarefa 3)

Status: **aprovada pelo dono em 01/10/2026**.

## Objetivo

Treinar a primeira árvore de decisão do projeto e entregar o que o diário da Tarefa 3 pede
(`docs/projeto_preditor_redes/tarefas/Tarefa3_Arvore_Inicial.md`, prazo 04/10/2026): a árvore, as regras lidas em
português, a matriz 3×3 na validação e uma árvore de contraste. Nada do X nem do Y é recalculado: a entrada é
`docs/data/gold/dataset_rotulado_B.parquet`, como está.

### Alvo: `status_futuro` (decisão do dono, 01/10/2026)

A árvore oficial é o **preditor**: com as métricas da medição atual, prevê a classe do mesmo fluxo 12 minutos
depois. Consequências:

- Só entram linhas com `status_futuro` preenchido (hoje: treino 34.898, validação 13.723, teste 20.507; depois da
  folga, a execução real usa treino 34.661 e validação 13.490).
- **Folga entre blocos (RFC §9):** em treino e validação, as 3 últimas medições de cada fluxo têm o futuro dentro do
  bloco seguinte. Elas são descartadas no treino e na medição da validação (cerca de 3 × 79 linhas por bloco; na execução real, 237 no
  treino e 233 na validação).
- **Comparação obrigatória com a persistência** (RFC §9, Tarefa 5 seção 4): a regra "o futuro é igual ao
  `status_atual`" é medida na mesma validação, com as mesmas métricas. Hoje ela acerta 80,6 % das linhas da validação (80,64 % depois da folga).
  Se a árvore não ganhar em F1 macro, o resultado é registrado assim mesmo: não se troca o alvo nem se mexe no rótulo
  para "melhorar" o número.
- `status_atual` e `regra` **não** são features (o diário pede conferir que a classe não entra como coluna).

### Colunas da árvore oficial (diário, seção 1)

`z_robusto`, `aumento_pct`, `jitter_relativo`, `perda_pct`, `timeout_atual`, `n5_timeout`, `n5_aumento80`,
`n5_moderado`. São as 8 do diário; `n5_risco` do diário é a coluna `n5_moderado` do dataset (mesma equivalência de
`SPEC-calculo-y.md`).

Ficam fora, mesmo existindo no dataset: `fluxo_id`, `prb_id`, `dst_addr`, `msm_id`, `rota`, `destination_country`,
`destination_region`, `rtt`, `jitter`, `t`, `periodo`, e também `latencia_relativa`, `tendencia`, `persistencia`,
`moderado`, `desviado` (não estão na lista do diário; a Tarefa 4 pode discutir incluí-las).

**Valores ausentes ficam ausentes.** Sem RTT, `z_robusto` e `aumento_pct` são nulos (190 linhas); `jitter_relativo`
é nulo em 776 e `n5_aumento80` em 12. A RFC §8.3 proíbe trocar RTT ausente por 0; a árvore recebe o nulo como está.

### Como a árvore é escolhida (diário, seção 2)

- CART com critério **Gini**, semente fixa (`SEMENTE = 16`, o número do grupo), sem balanceamento de classes.
- `fit` só no bloco `treino`.
- Grade: `max_depth` ∈ {2, 3, 4, 5, 6, 8, 10} × `min_samples_leaf` ∈ {50, 100, 200, 500} (28 árvores). Vence a de
  maior **F1 macro na validação**; empate → a mais rasa, depois a de folha maior. A tabela inteira da busca é gravada.
- Saem: critério, `max_depth` pedido, profundidade obtida, número de folhas, as divisões dos dois primeiros níveis e
  as regras completas em texto.
- **Regras em português:** as 3 folhas com mais linhas de treino, uma por classe quando existir, escritas a partir do
  caminho real da raiz à folha ("se `z_robusto` ≤ 3,41 e `n5_moderado` ≤ 1,5 então OK"), com N e pureza da folha.

### Leitura do erro (diário, seção 3), só na validação

- Matriz 3×3 em contagem (linha = classe verdadeira, coluna = classe prevista), na ordem OK, RISCO, FALHA.
- Precisão, recall e F1 por classe; F1 macro; balanced accuracy; acurácia (impressa, mas não decide nada).
- As mesmas métricas para a persistência, lado a lado.
- Dois erros concretos, escolhidos de forma determinística (primeiro de uma lista ordenada):
  - caminho longo e estável que a árvore mandou para FALHA: fluxo com mediana do baseline acima da mediana das
    medianas, `|z_robusto|` ≤ 1 (`EXEMPLO_OK_Z_MAX`), verdadeiro OK, previsto FALHA; o de maior `rtt`;
  - FALHA de caminho curto que a árvore mandou para OK: fluxo com mediana abaixo da mediana das medianas, verdadeiro
    FALHA, previsto OK; o de menor `rtt`.
  - Se um dos casos não existir na validação, o programa diz isso em vez de inventar.
  - `fluxo_id`, `t` e `rtt` aparecem só para localizar a linha (a mediana vem de `baseline_por_fluxo.parquet`).
- O bloco `teste` **não é medido**: fica fechado até a Tarefa 5.

### Árvore de contraste (diário, seção 4)

Mesmo treino, mesmo alvo, mesmos hiperparâmetros da oficial, com as 8 colunas mais `rtt` (ms) e
`destination_region` (uma coluna 0/1 por região). Saem: a divisão da raiz e dos dois primeiros níveis, a importância
de cada coluna extra e o F1 macro na validação. O programa imprime o que a árvore fez de fato; se ela **não** usar
`rtt` nem região perto da raiz, isso é o resultado a relatar. Ela não é gravada como modelo e não vai adiante.

### Fora do escopo

- Outro algoritmo (floresta, boosting), balanceamento de classes, limiar fino, poda por custo: Tarefa 4.
- Medir o teste, Protocolo B (fluxos novos), ficha da árvore: Tarefa 5.
- Mudar qualquer coisa do Bronze, Silver ou Gold.
- Preencher o diário: o programa imprime tudo pronto para colar; o texto é do grupo.

## Stack

Python 3.11+ e `uv`. O pipeline de dados continua em PySpark. A árvore é treinada com **scikit-learn**
(`DecisionTreeClassifier`), lendo o Parquet do Gold com pandas + pyarrow. Dependências novas em `pyproject.toml`:
`scikit-learn>=1.4`, `pandas`, `pyarrow` (aprovadas pelo dono em 01/10/2026).

## Comandos

```bash
uv sync
uv run python -m preditor arvore   # docs/data/gold/ → docs/data/modelo/ (offline, sem Spark nem Java)
```

`arvore` não entra na execução sem argumento (que continua sendo bronze → silver → gold). Sem o Gold no disco,
termina com a mensagem "Rode antes: uv run python -m preditor gold".

## Estrutura do projeto

```
src/preditor/
  config.py              → colunas da árvore, colunas proibidas, grade, semente, caminhos de docs/data/modelo/
  modelo/__init__.py
  modelo/dados.py        → classe DadosModelo: lê o Gold, aplica a folga, descarta futuro nulo, separa X e y por bloco
  modelo/arvore.py       → classe Arvore: busca na grade, treino, regras em texto e em português
  modelo/regras.py       → classes Condicao e Regra, e Regras: as 3 regras em português (caminho, fusão de condições repetidas, texto) e a checagem delas
  modelo/avaliacao.py    → classe Avaliacao: matriz 3×3, métricas, persistência, erros concretos
  modelo/execucao.py     → classe ExecucaoArvore: orquestra, grava e verifica (decisão do plano)
  __main__.py            → opção `arvore`: chama ExecucaoArvore sem subir o Spark
docs/data/modelo/        (ignorado pelo git)
  busca_hiperparametros.csv   → as 28 combinações com F1 macro de treino e de validação
  arvore_oficial.json         → critério, hiperparâmetros, profundidade, folhas, semente, colunas
  regras_arvore_oficial.txt   → a árvore inteira em texto + as 3 regras em português
  matriz_validacao.csv        → matriz 3×3 da persistência, da árvore e do contraste
  metricas_validacao.csv      → precisão, recall, F1 por classe, F1 macro, balanced accuracy (árvore, persistência, contraste)
  regras_arvore_contraste.txt → a árvore de contraste em texto
```

## Estilo de código

Segue o `AGENTS.md`: português, um passo por linha, comentário dizendo o porquê, constantes em `config.py`.

```python
# Diário da Tarefa 3, seção 1: só métricas relativas ao baseline do fluxo.
# `n5_moderado` é o `n5_risco` do diário (SPEC-calculo-y.md).
COLUNAS_ARVORE = [
    "z_robusto", "aumento_pct", "jitter_relativo", "perda_pct",
    "timeout_atual", "n5_timeout", "n5_aumento80", "n5_moderado",
]

# modelo/arvore.py
arvore = DecisionTreeClassifier(
    criterion=config.CRITERIO,          # "gini"
    max_depth=profundidade,
    min_samples_leaf=folha_minima,
    random_state=config.SEMENTE,        # mesma árvore a cada execução
)
# fit só no treino: validação e teste nunca passam por aqui.
arvore.fit(treino[config.COLUNAS_ARVORE], treino["status_futuro"])
```

## Estratégia de testes

Sem framework de testes. A verificação é rodar `uv run python -m preditor arvore`, que para com `assert` se:

- o X oficial não tiver exatamente as 8 colunas, ou tiver alguma coluna da lista de proibidas;
- houver linha de `validacao` ou `teste` no `fit`, ou linha de `teste` em qualquer métrica;
- sobrar `status_futuro` nulo, ou alguma das 3 últimas medições de um fluxo em treino/validação (folga);
- algum bloco usado ficar sem uma das três classes;
- a matriz não somar o N da validação, ou o F1 macro não bater com a média dos três F1 recalculados da matriz;
- os hiperparâmetros gravados não forem a melhor linha de `busca_hiperparametros.csv`;
- as regras em texto citarem coluna fora das permitidas;
- treinar de novo com a mesma semente der uma árvore diferente.

## Limites

- **Sempre:** `fit` só no treino; escolha de hiperparâmetros só pela validação; medir a persistência junto;
  constantes em `config.py` com a origem; atualizar `AGENTS.md` e `README.md`.
- **Perguntar antes:** adicionar dependências além das aprovadas; mudar a lista de colunas, a grade ou o alvo;
  preencher valor ausente; balancear classes; qualquer mudança no Gold.
- **Nunca:** ler o bloco `teste` para medir ou escolher; usar país, região, IP, `fluxo_id` ou `rtt` na árvore oficial;
  usar `status_atual` ou `regra` como feature; commitar dados ou modelos.

## Critérios de sucesso

- [x] `uv run python -m preditor arvore` roda offline e passa em todas as checagens.
- [x] A saída mostra as 8 colunas, critério, `max_depth` pedido e obtido, folhas e as divisões dos dois primeiros níveis.
- [x] Três regras em português copiadas da árvore, com N e pureza.
- [x] Matriz 3×3 em contagem e precisão / recall / F1 por classe + F1 macro, na validação, para árvore e persistência.
- [x] Dois erros concretos (ou a frase "não apareceu na validação").
- [x] Árvore de contraste: raiz, dois primeiros níveis, importância de `rtt` e região, F1 macro.
- [x] Nenhum número do bloco `teste` aparece na saída além do N.
- [x] `AGENTS.md` (estágio, comando, decisões) e `README.md` descrevem a árvore.

## Decisões fechadas (01/10/2026)

1. **Alvo:** `status_futuro` (preditor de 12 min).
2. **Contraste:** `rtt` + `destination_region`.
3. **Biblioteca:** scikit-learn (comparação com o Spark MLlib no fim).
4. **Premissas abaixo confirmadas**, incluindo treinar sem balanceamento de classes (o balanceamento fica para a
   Tarefa 4, como ajuste medido contra esta árvore).

## Premissas (confirmadas pelo dono em 01/10/2026)

1. A folga é aplicada descartando as 3 últimas medições de cada fluxo em treino e validação.
2. As 8 colunas do diário, sem `status_atual` e sem `tendencia` / `persistencia` / `latencia_relativa`.
3. Gini, sem balanceamento, semente 16, grade de 28 combinações, desempate pela árvore mais simples.
4. "Caminho longo / curto" = mediana do baseline do fluxo acima / abaixo da mediana das medianas.
5. `arvore` é um comando à parte, fora da execução sem argumento.
6. O modelo não é gravado em arquivo binário: a semente fixa refaz a mesma árvore; ficam os parâmetros em JSON.

## Comparação que levou à escolha da biblioteca

Escolhida: **scikit-learn**.

| | scikit-learn | Spark MLlib |
|---|---|---|
| Dependências | + `scikit-learn`, `pandas`, `pyarrow` | nenhuma nova |
| Nomes do diário | `max_depth`, `min_samples_leaf`: iguais | `maxDepth`, `minInstancesPerNode` |
| Valor ausente | aceito na árvore, sem imputar | não aceito: obriga a imputar ou descartar linhas (190 sem RTT) |
| Regras em texto | `export_text` com o nome das colunas | `toDebugString` com "feature 3"; traduzir à mão |
| Métricas | `confusion_matrix`, `classification_report` prontos | montar com `groupBy` ou `MulticlassMetrics` |
| Execução | segundos, sem Java | sobe uma sessão Spark para 70 mil linhas |
| Coerência do projeto | duas ferramentas (Spark nos dados, sklearn no modelo) | tudo em PySpark |
| Tarefas 4 e 5 | poda, `class_weight`, `GroupKFold` (Protocolo B) prontos | poda por custo e split por grupo não existem prontos |

