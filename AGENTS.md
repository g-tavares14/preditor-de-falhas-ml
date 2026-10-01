# AGENTS.md

Instructions for AI agents working in this repository (Claude Code loads it through `CLAUDE.md`).

## Project

Projeto acadêmico (grupo 16): classificar o estado de rotas de rede em **OK / RISCO / FALHA** a partir de
medições públicas de ping do RIPE Atlas, com uma árvore de decisão. O "normal" de cada rota é aprendido dela
mesma, então o modelo usa métricas **relativas ao baseline de cada fluxo**, não limites fixos em ms.

Estágio atual: o pipeline segue a arquitetura medalhão (`SPEC-medalhao.md`): Bronze (cópia do BigQuery),
Silver (normalização) e o Gold (cálculo do X: baseline + features; cálculo do Y: rótulo OK / RISCO / FALHA em
`src/preditor/gold/calculo_y/`, spec em `SPEC-calculo-y.md`) estão prontos. A árvore vem depois.

A pergunta, as regras de rótulo e a origem dos dados estão em `docs/` (índice em `docs/README.md`; a RFC em
`docs/projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md` é a referência das fórmulas, §8.2 a §8.4).

## Stack

- Python 3.11, gerenciado com `uv` (build backend `uv_build`, pacote `preditor` em `src/`).
- PySpark 3.5 em modo local; só a camada Bronze lê do BigQuery, via conector Spark (baixado na primeira execução).
- Java 17 (exigido pelo Spark) e `gcloud auth application-default login` para as credenciais do BigQuery (só o Bronze).
- Fonte: tabela `atlas-ripe-509700.atlasRipe.atlas`, região EU.
- Notebooks (grupo `notebook`: `requests`, `pandas`, `ipykernel`) usam a API do RIPE Atlas diretamente.
- Sem framework de testes, linter ou type-checker configurados.

## Commands

```bash
# install:
uv sync
# install (notebooks):
uv sync --group notebook
# run (pipeline completo: bronze → silver → gold):
uv run python -m preditor
# run (uma camada; cada uma lê a anterior do disco):
uv run python -m preditor bronze   # BigQuery → docs/data/bronze/ (rede + gcloud)
uv run python -m preditor silver   # docs/data/bronze/ → docs/data/silver/ (offline)
uv run python -m preditor gold     # docs/data/silver/ → docs/data/gold/ (offline; inclui dataset_rotulado_B.parquet
                                   # e contagem_classes.csv)
# typecheck: não há
# lint: não há
# test: não há — a verificação é rodar o pipeline; cada camada termina com checagens automáticas
#       (Bronze: linhas e colunas = BigQuery; Silver: nenhum rtt <= 0, nenhum par (fluxo_id, t) repetido, 82 fluxos;
#        Gold: Período A não vaza para as features, 81 fluxos no baseline, 2 insuficientes; rótulo: mesmas linhas
#        das features, regra ↔ classe, FALHA com precedência, status_futuro conferido por um caminho independente
#        do lead, blocos em ordem de tempo, cada bloco com as 3 classes. O gold imprime também 3 exemplos reais)
```

Só `bronze` (e o pipeline completo) precisa de rede e credenciais do BigQuery. `silver` e `gold` rodam offline, mas
exigem a camada anterior no disco: sem ela, terminam com a mensagem de qual comando rodar antes (nunca recaem no
BigQuery). Sem rede, verifique ao menos a importação: `uv run python -c "import preditor.__main__"`.

## Conventions

- Código, nomes, comentários e docs em português (ex.: `calculo_x`, `baseline_insuficiente`, `fluxo_id`).
- Cada camada do pipeline fica em sua pasta: `bronze/` → `silver/` → `gold/` (o Gold tem `calculo_x/` e `calculo_y/`
  dentro); `__main__.py` orquestra, grava e verifica. Cada camada lê a anterior do disco, nunca da memória.
- Todo "número mágico" vai para `src/preditor/config.py`, com comentário dizendo a origem (seção da RFC ou decisão).
- O código comenta cada passo, mas não repete a teoria da RFC: referencia a seção.
- Saídas vão para `docs/data/{bronze,silver,gold}/` (ignoradas pelo git): Parquet para dados, CSV só para leitura humana.
- O dono está começando em PySpark: prefira transformações legíveis e explicadas a construções compactas.

## Decisions

- **Dataset de 7 dias** (18/09 a 25/09/2026). Período A = primeiras **108 h** (menor corte em que todos os fluxos
  passam de 1.500 RTT válidos); Período B = o restante. As datas de corte da RFC são de uma coleta anterior.
- **RTT válido** = `rtt > 0` e `timeout = false` (no Atlas, timeout vem com `rtt = 0.0`).
- **RTT da medição** = média dos pings válidos da rajada; **jitter** = média de |Δrtt| entre pings consecutivos.
- **`fluxo_id` = `prb_id|dst_addr|msm_id`**: 81 fluxos no baseline (79 com baseline, 2 com `baseline_insuficiente`);
  o Silver tem 82 `fluxo_id`, o 82º só com medições no Período B, fora do modelo.
- **Arquitetura medalhão**: o Bronze copia a tabela inteira do BigQuery, sem filtro (lido uma vez); o Silver tem uma
  linha por medição; o Gold tem baseline, features, `limites_por_regiao.csv` e o dataset rotulado.
- **Duplicatas removidas no Silver** (`dropDuplicates()`): 63 linhas idênticas vindas da tabela de origem (9 no
  Período A, 54 no B). Sem isso a janela das "últimas 5" contava a medição duas vezes e a "3ª medição à frente"
  ficava ambígua. Com a remoção, `features_B` tem 70.616 linhas; os 82 / 81 / 2 fluxos e o corte A/B não mudam.
- **As checagens de contagem em `config.py`** (`FLUXOS_SILVER` = 82, `FLUXOS_BASELINE` = 81, `FLUXOS_INSUFICIENTES` = 2)
  valem para este dataset de 7 dias. Se a coleta for refeita, elas falham de propósito: revise-as junto com as decisões.
- **`status_atual`** = tabela da RFC §8.4 aplicada na ordem (a primeira linha verdadeira decide); a coluna `regra`
  (1 a 6) guarda qual linha disparou e a classe é derivada dela. O Y só lê colunas do X, não recalcula métrica.
- **Limitação conhecida da regra 3** (`z_robusto` ≥ 3,5, sem piso em ms nem em %): 88 % dessas FALHAs têm
  `aumento_pct` < 30 % (fluxos muito estáveis, com MAD pequeno). O dono decidiu seguir a regra da professora.
- **`status_futuro`** = `status_atual` da 3ª medição seguinte do mesmo fluxo, só se ela estiver de 600 a 840 s
  depois (RFC §3); senão é nulo. Linhas com futuro nulo ficam no dataset: o treino do preditor as descarta.
- **`bloco`** (treino / validacao / teste): dois instantes de corte globais, iguais para todos os fluxos, a 50 % e
  70 % do intervalo entre o menor e o maior `t` do dataset rotulado; sem sorteio e **sem folga entre blocos** (RFC
  §9). Em treino e validação, as 3 últimas medições de cada fluxo têm `status_futuro` vindo do bloco seguinte (a spec
  da árvore decide o que fazer); no teste, esse futuro é nulo (fim da série).
- **Região e país são metadados, não features**: a RFC proíbe usá-los na árvore.
- O baseline usa só o Período A; nada do Período A pode entrar nas features do Período B.
- Os notebooks `01`–`03` são entregas da primeira fase no formato pedido pela professora: fazem GET/POST na API do
  RIPE Atlas e não usam o BigQuery nem `src/preditor`. Não os migre para o pipeline.

## Security rules

- Nunca versionar credenciais: `RIPE_ATLAS_API_KEY` fica no ambiente ou em `.env` (ignorado pelo git); o BigQuery
  usa as credenciais padrão do gcloud, sem arquivo de chave no repositório.
- Não commitar dados de nenhuma camada (`docs/data/raw/*`, `docs/data/{bronze,silver,gold}/`), só os READMEs e docs.
- Não imprimir chaves ou tokens em logs, notebooks ou saídas de célula.

## Agent workflow

- Lifecycle: `/spec` → `/plan` → `/build` → `/verify` → `/review`. Specs live in the repo; the plan in `tasks/plan.md`, tasks in `tasks/todo.md` (the Y spec uses `tasks/plan-calculo-y.md` and `tasks/todo-calculo-y.md`).
- Agents: `implementer` implements one task and stops for review; `reviewer` reviews the diff without editing.
- Skills live in `.claude/skills/` and belong to this project: adapt them freely. `.claude/catalog.md` lists catalog skills not installed yet.
- Do not commit or push without the owner asking.
