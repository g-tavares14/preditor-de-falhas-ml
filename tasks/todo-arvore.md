# Tarefas: árvore inicial (Tarefa 3)

Plano: [`plan-arvore.md`](plan-arvore.md) · Spec: [`SPEC-arvore.md`](../SPEC-arvore.md)

Verificação padrão de toda tarefa (o projeto não tem testes nem linter): `uv run python -c "import preditor.__main__"`
e `uv run python -m preditor arvore` (offline, sem Spark nem Java, a partir do Gold que já está no disco).

---

## ✅ A1: Dependências, leitura dos dados e comando `arvore`

**Descrição:** Adicionar `scikit-learn>=1.4`, `pandas` e `pyarrow` às dependências (`uv add`). Criar
`modelo/dados.py` com a classe `DadosModelo`: lê `dataset_rotulado_B.parquet`, marca as 3 últimas medições de cada
(`fluxo_id`, `bloco`) no dataset inteiro ordenado por `t` (folga, RFC §9), só depois descarta `status_futuro` nulo,
e devolve X (as 8 colunas) e y por bloco. Criar `modelo/execucao.py` (`ExecucaoArvore`) e a opção `arvore` em
`__main__.py`, desviando antes de `build_spark`.

**Critérios de aceite:**
- [ ] `config.py` tem `COLUNAS_ARVORE` (8 colunas, origem: diário da Tarefa 3, seção 1), `COLUNAS_PROIBIDAS`, `ALVO`,
      `CLASSES`, `MODELO` (pasta `docs/data/modelo/`); a folga usa `PASSOS_FUTURO`
- [ ] O comando roda sem Java e sem criar sessão Spark; sem o Gold, termina com "Rode antes: uv run python -m
      preditor gold"
- [ ] Checagens automáticas: X com exatamente `COLUNAS_ARVORE`; nenhuma coluna proibida; nenhum `status_futuro`
      nulo; nenhuma das 3 últimas medições de um fluxo em treino ou validação; treino e validação com as 3 classes
- [ ] Imprime o N por bloco e por classe, e quantas linhas saíram por futuro nulo e por folga
- [ ] Nenhum valor ausente é preenchido (X em `float64`, com `NaN`)
- [ ] O bloco `teste` só aparece como N

**Verificação:**
- [ ] `uv run python -m preditor arvore`
- [ ] `JAVA_HOME= uv run python -m preditor arvore` também roda
- [ ] `uv run python -m preditor gold` continua passando
- [ ] Se o `uv add` não achar pacote para o Python do `.venv`: parar e perguntar ao dono

**Dependências:** nenhuma
**Arquivos:** `pyproject.toml`, `uv.lock`, `src/preditor/config.py`, `src/preditor/modelo/__init__.py`,
`src/preditor/modelo/dados.py`, `src/preditor/modelo/execucao.py`, `src/preditor/__main__.py`
**Escopo:** médio

## ✅ A2: Métricas e persistência

**Descrição:** Criar `modelo/avaliacao.py` com a classe `Avaliacao`. `medir(verdadeiro, previsto)` devolve a matriz
3×3 em contagem (linha = verdadeiro, coluna = previsto, ordem OK / RISCO / FALHA), precisão, recall e F1 por classe,
F1 macro, balanced accuracy e acurácia. Aplicar à persistência (previsão = `status_atual`) na validação e gravar
`matriz_validacao.csv` e `metricas_validacao.csv`.

**Critérios de aceite:**
- [ ] Checagens automáticas: a matriz soma o N da validação; o F1 macro bate com a média dos 3 F1 recalculados da
      matriz; nenhuma linha de `teste` é medida (a função recusa)
- [ ] Saída impressa legível: matriz com rótulos de linha e coluna, tabela por classe
- [ ] Os dois CSVs gravados em `docs/data/modelo/`, com uma coluna dizendo o modelo (`persistencia`)

**Verificação:**
- [ ] `uv run python -m preditor arvore`
- [ ] Acurácia da persistência perto de 80,6 % (difere um pouco por causa da folga)

**Dependências:** A1
**Arquivos:** `src/preditor/modelo/avaliacao.py`, `src/preditor/modelo/execucao.py`, `src/preditor/config.py`
**Escopo:** pequeno

## ✅ A3: Árvore oficial

**Descrição:** Criar `modelo/arvore.py` com a classe `Arvore`. Treinar, só no treino, as 28 combinações de
`max_depth` ∈ {2, 3, 4, 5, 6, 8, 10} × `min_samples_leaf` ∈ {50, 100, 200, 500} (Gini, `random_state = SEMENTE`),
medir cada uma na validação e escolher a de maior F1 macro (empate: menor profundidade, depois folha maior). Gravar
`busca_hiperparametros.csv`, `arvore_oficial.json` e `regras_arvore_oficial.txt` (`export_text`). As métricas da
árvore entram nos dois CSVs da A2, ao lado da persistência.

**Critérios de aceite:**
- [ ] `config.py` tem `CRITERIO`, `SEMENTE = 16`, `GRADE_PROFUNDIDADE`, `GRADE_FOLHA_MINIMA`, com a origem
- [ ] Imprime critério, `max_depth` pedido e obtido, número de folhas e as divisões dos dois primeiros níveis
- [ ] Imprime árvore × persistência lado a lado (F1 por classe, F1 macro, balanced accuracy)
- [ ] Checagens automáticas: `fit` só com linhas de `treino`; a escolhida é a primeira linha da busca ordenada; as
      regras só citam `COLUNAS_ARVORE`; treinar de novo com a mesma semente dá a mesma árvore
- [ ] Sem `class_weight` (decisão do dono, 01/10/2026)

**Verificação:**
- [ ] Rodar duas vezes e comparar `docs/data/modelo/` com `diff`
- [ ] Prova de que uma checagem falha com dado errado (ex.: incluir `rtt` nas colunas, só em memória)

**Dependências:** A2
**Arquivos:** `src/preditor/modelo/arvore.py`, `src/preditor/modelo/execucao.py`, `src/preditor/config.py`
**Escopo:** médio

## Checkpoint A (revisão do dono)
- [x] Árvore × persistência na validação conferida (dono, 01/10/2026: F1 macro 0,7457 × 0,7221; segue com esta árvore)
- [x] Árvore escolhida (profundidade, folhas, primeiras divisões) conferida (`max_depth` 4, `min_samples_leaf` 50, 16 folhas)
- [x] Se a árvore perder da persistência: registrado assim; alvo, colunas e grade só mudam com nova decisão (não se aplica: a árvore ganhou)

---

## ✅ A4: Regras em português e erros concretos

**Descrição:** Em `Arvore`, escrever as 3 folhas com mais linhas de treino (uma por classe quando existir) como
"se `métrica` ≤ limiar e … então CLASSE", a partir do caminho real em `arvore.tree_`, com N e pureza; anexar a
`regras_arvore_oficial.txt`. Em `Avaliacao`, achar dois erros da validação: (1) caminho longo e estável previsto
FALHA (mediana do baseline acima da mediana das medianas, `|z_robusto|` ≤ `EXEMPLO_OK_Z_MAX`, verdadeiro OK; o de
maior `rtt`); (2) FALHA de caminho curto prevista OK (mediana abaixo; o de menor `rtt`).

**Critérios de aceite:**
- [ ] Checagem automática: aplicar cada regra ao treino seleciona exatamente as linhas daquela folha
- [ ] Erros escolhidos de forma determinística, impressos com `fluxo_id`, `t`, métricas, classe verdadeira e prevista
- [ ] Se um caso não existir, o programa imprime "não apareceu na validação"
- [ ] `fluxo_id`, `rtt` e a mediana só localizam e classificam o erro: não entram na árvore

**Verificação:**
- [ ] Rodar duas vezes: mesma saída
- [ ] Conferir uma regra à mão contra o `export_text`

**Dependências:** A3
**Arquivos:** `src/preditor/modelo/arvore.py`, `src/preditor/modelo/avaliacao.py`, `src/preditor/modelo/execucao.py`
**Escopo:** médio

## ✅ A5: Árvore de contraste

**Descrição:** Treinar outra árvore no mesmo treino, com os hiperparâmetros da oficial, usando as 8 colunas mais
`rtt` e `destination_region` (colunas 0/1, categorias fixadas pelo treino). Gravar `regras_arvore_contraste.txt` e
acrescentar as métricas a `metricas_validacao.csv`.

**Critérios de aceite:**
- [ ] `config.py` tem `COLUNAS_CONTRASTE` (origem: diário, seção 4, e decisão do dono)
- [ ] Imprime a raiz, os dois primeiros níveis, a importância de `rtt` e de cada região, e o F1 macro na validação
- [ ] Imprime que a árvore de contraste fica fora da entrega; se `rtt` / região não aparecerem perto da raiz, diz isso
- [ ] A árvore oficial e os arquivos dela não mudam

**Verificação:**
- [ ] `diff` dos arquivos da árvore oficial antes e depois

**Dependências:** A4
**Arquivos:** `src/preditor/modelo/dados.py`, `src/preditor/modelo/arvore.py`, `src/preditor/modelo/regras.py`,
`src/preditor/modelo/execucao.py`, `src/preditor/config.py`
**Escopo:** pequeno

## ✅ A6: Documentação e fechamento

**Descrição:** Atualizar `AGENTS.md` (estágio atual, stack, comando `arvore`, decisões: alvo `status_futuro`, folga,
sem balanceamento, comparação com a persistência) e `README.md` (comando e saídas de `docs/data/modelo/`). Marcar os
critérios de sucesso de `SPEC-arvore.md` e anotar os números de referência no fim deste arquivo.

**Critérios de aceite:**
- [ ] `AGENTS.md` não diz mais "A árvore vem depois"
- [ ] `README.md` lista o comando `arvore` e os arquivos de `docs/data/modelo/`
- [ ] Números de referência anotados: N por bloco depois da folga, hiperparâmetros escolhidos, F1 macro da árvore,
      da persistência e do contraste
- [ ] Critérios de sucesso de `SPEC-arvore.md` marcados

**Verificação:**
- [ ] `uv run python -c "import preditor.__main__"` e `uv run python -m preditor arvore`
- [ ] `git status` sem nada de `docs/data/`

**Dependências:** A5
**Arquivos:** `AGENTS.md`, `README.md`, `SPEC-arvore.md`, `tasks/todo-arvore.md`
**Escopo:** pequeno

## Checkpoint final
- [ ] Todos os critérios de sucesso de `SPEC-arvore.md` marcados
- [ ] Pronto para `/review`

---

## Números de referência

Lidos da execução de `uv run python -m preditor arvore` (01/10/2026) e de `docs/data/modelo/`. São resultado, não
constantes: se o Gold for refeito, mudam. Dataset de 7 dias, semente 16, sem `class_weight`.

**N por bloco (alvo `status_futuro`, depois da folga)**

| bloco | linhas | futuro nulo | folga | N usado |
|---|---|---|---|---|
| treino | 35.372 | 474 | 237 | 34.661 |
| validação | 14.096 | 373 | 233 | 13.490 |
| teste | | | | 20.507 (só o N; fechado até a Tarefa 5) |

| bloco | OK | RISCO | FALHA | total |
|---|---|---|---|---|
| treino | 21.869 | 5.084 | 7.708 | 34.661 |
| validação | 8.145 | 1.609 | 3.736 | 13.490 |

**Árvore oficial:** Gini, `max_depth` pedido 4, `min_samples_leaf` 50; profundidade obtida 4; 16 folhas. Raiz:
`z_robusto` ≤ 2,02 (N = 34.661); filhos: `n5_moderado` ≤ 2,50 (N = 24.090) e `z_robusto` ≤ 3,83 (N = 10.571).

**Validação (N = 13.490): F1 por classe, F1 macro e balanced accuracy**

| | persistência | árvore oficial | contraste |
|---|---|---|---|
| F1 OK | 0,8674 | 0,8869 | 0,8958 |
| F1 RISCO | 0,4902 | 0,5393 | 0,5687 |
| F1 FALHA | 0,8087 | 0,8109 | 0,8217 |
| **F1 macro** | **0,7221** | **0,7457** | **0,7620** |
| balanced accuracy | 0,7217 | 0,7293 | 0,7437 |
| acurácia (informativa) | 0,8064 | 0,8290 | 0,8403 |

A árvore oficial ganha da persistência em F1 macro (+0,0236); o contraste ganha da oficial (+0,0163).

**Três primeiras linhas da busca** (`busca_hiperparametros.csv`, 28 combinações ordenadas por F1 macro na validação)

| max_depth | min_samples_leaf | obtida | folhas | F1 treino | F1 validação |
|---|---|---|---|---|---|
| 4 | 50 | 4 | 16 | 0,7293 | 0,7457 (escolhida) |
| 4 | 200 | 4 | 16 | 0,7277 | 0,7448 |
| 4 | 100 | 4 | 16 | 0,7289 | 0,7447 |

**Regras em português** (folhas de treino mais cheias, uma por classe)

1. se `z_robusto` ≤ 2,0158 e `n5_moderado` ≤ 0,50 e `n5_aumento80` ≤ 0,50 (ou ausente) então **OK**
   (N = 11.417; pureza 93,3 %).
2. se `z_robusto` > 2,0158 e `z_robusto` ≤ 3,83 e `n5_moderado` > 4,50 então **RISCO** (N = 1.605; pureza 72,4 %).
3. se `z_robusto` > 3,83 (ou ausente) e `jitter_relativo` ≤ 3,0574 (ou ausente) e `n5_moderado` ≤ 2,50 então
   **FALHA** (N = 3.994; pureza 90,8 %).

**Erros concretos na validação** (mediana das medianas dos 79 fluxos com baseline = 209,73 ms)

- Erro 1 (caminho longo e estável previsto FALHA, verdadeiro OK): **não apareceu na validação** (nenhuma linha atende).
- Erro 2 (FALHA de caminho curto prevista OK; 442 linhas atendem, a de menor `rtt`): fluxo `6891|150.164.1.222|28095697`,
  `t` = 2026-09-24 00:24:03, `rtt` 0,12 ms, mediana do fluxo 0,40 ms. Métricas: `z_robusto` -1,012, `aumento_pct`
  -70,45, `jitter_relativo` 0,05, `perda_pct` 0, `timeout_atual` 0, `n5_timeout` 0, `n5_aumento80` 1, `n5_moderado` 1.
  `status_atual` OK, verdadeiro (`status_futuro`) FALHA, previsto OK.

**Árvore de contraste** (13 colunas: as 8 + `rtt` + 4 regiões; mesmos hiperparâmetros, 16 folhas): a raiz continua
`z_robusto` ≤ 2,02, e os 2 primeiros níveis são iguais aos da oficial. `rtt` divide pela primeira vez no nível 3
(fora dos 2 primeiros). Importâncias: `rtt` 0,0667; as 4 colunas de região 0,0000 (nenhuma região divide em nível
algum). Fora da entrega: não é o modelo do projeto.
