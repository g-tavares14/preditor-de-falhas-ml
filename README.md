# Preditor de falhas ML

Projeto acadêmico: classificar o estado de rotas de rede (**OK / RISCO / FALHA**)
a partir de medições públicas de ping do RIPE Atlas, com uma árvore de decisão.

O "normal" de cada rota é aprendido dela mesma: 110 ms é saudável em
Brasil → EUA e seria dez vezes o normal em Brasil → Brasil. Por isso o modelo
usa métricas **relativas ao baseline de cada fluxo**, e não limites fixos em ms.

A pergunta, as regras de rótulo e a origem dos dados estão em [`docs/`](docs/README.md).
Este README cobre só o código: como rodar e o que ele produz.

## Organização do repositório

| Pasta | O que é |
|---|---|
| `src/preditor/` | Código-fonte do projeto (pipeline em PySpark) |
| `docs/` | Documentação acadêmica e dos dados, com índice em [`docs/README.md`](docs/README.md) |
| `notebooks/` | Entregas da primeira fase, no formato pedido pela professora: 01 (GET) e 02 (POST) direto na API do RIPE Atlas, 03 (rótulo `status_real` por limiar fixo). Não usam o BigQuery nem `src/preditor` |
| `docs/data/{bronze,silver,gold}/` | Saídas de cada camada do pipeline (ignoradas pelo git) |

## Ambiente

Pré-requisitos:

- [uv](https://docs.astral.sh/uv/): gerencia Python 3.11 e as dependências (`pyspark` 3.5).
- **Java 17**, exigido pelo Spark:

  ```bash
  brew install openjdk@17
  echo 'export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home' >> ~/.zshrc
  ```

  Se o `java` não estiver no PATH (o `openjdk@17` do Homebrew fica instalado mas não
  linkado), exporte o `JAVA_HOME` acima antes de rodar o pipeline.

- **gcloud autenticado** (só para a camada Bronze): o conector do BigQuery usa as
  credenciais padrão, sem arquivo de chave.

  ```bash
  gcloud auth application-default login
  ```

Instalação:

```bash
uv sync
```

Os notebooks usam um grupo de dependências separado (`requests`, `pandas`,
`ipykernel`) e a chave `RIPE_ATLAS_API_KEY` no ambiente ou em `.env`:

```bash
uv sync --group notebook
```

## Executar

O pipeline segue a arquitetura medalhão: três camadas, cada uma gravada em disco e
lida pela seguinte (detalhes em [`SPEC-medalhao.md`](SPEC-medalhao.md)).

```bash
uv run python -m preditor          # bronze → silver → gold
uv run python -m preditor bronze   # lê o BigQuery e grava docs/data/bronze/ (rede e gcloud)
uv run python -m preditor silver   # lê o Bronze do disco e grava docs/data/silver/ (offline)
uv run python -m preditor gold     # lê o Silver do disco e grava docs/data/gold/ (offline)
```

Só o `bronze` precisa de rede e de credenciais. Na primeira execução o Spark baixa o
conector do BigQuery, o que leva alguns minutos. `silver` e `gold` rodam offline, mas
precisam da camada anterior no disco: sem ela, terminam dizendo qual comando rodar antes.

| Camada | Arquivo | Uma linha por | Conteúdo |
|---|---|---|---|
| Bronze | `docs/data/bronze/atlas.parquet` | medição bruta | Cópia fiel de `atlas-ripe-509700.atlasRipe.atlas` (região EU), sem filtro, com `pings` aninhado |
| Silver | `docs/data/silver/medicoes.parquet` | medição | `fluxo_id`, metadados da rota, `rtt`, `jitter`, `perda_pct` e `periodo` (A ou B); linhas duplicadas da tabela de origem são removidas |
| Gold | `docs/data/gold/baseline_por_fluxo.parquet` | fluxo | Ficha do Período A: mediana, MAD, IQR, jitter e perda típicos, taxa de resposta, `baseline_insuficiente` |
| Gold | `docs/data/gold/features_B.parquet` | medição do Período B | O **X** do modelo: `latencia_relativa`, `aumento_pct`, `z_robusto`, `jitter_relativo`, `n5_*`, `tendencia`, `persistencia` |
| Gold | `docs/data/gold/limites_por_regiao.csv` | rota / país | Os limiares da regra traduzidos para ms, por região (só para leitura) |
| Gold | `docs/data/gold/dataset_rotulado_B.parquet` | medição do Período B | O X (`features_B`) mais o **Y**: `regra` (1 a 6, a linha da tabela da RFC §8.4 que decidiu), `status_atual` (OK / RISCO / FALHA), `status_futuro` (o `status_atual` da 3ª medição à frente, 12 min depois; nulo se não existir ou houver lacuna) e `bloco` (treino / validacao / teste, por dois cortes de tempo iguais para todos os fluxos) |
| Gold | `docs/data/gold/contagem_classes.csv` | bloco | N de cada bloco por classe, com início, fim e os dois instantes de corte (só para leitura) |

Cada camada termina com checagens automáticas: o Bronze tem as mesmas linhas e colunas
do BigQuery; o Silver não tem `rtt <= 0` (nenhum timeout entra como RTT válido), não repete
nenhum par (`fluxo_id`, `t`) e tem 82 fluxos; no Gold, o Período A não pode vazar para as
features, o baseline tem 81 fluxos (2 insuficientes) e o dataset rotulado tem as mesmas
linhas das features, com `regra` e `status_atual` coerentes, `status_futuro` conferido por
um caminho independente e os blocos em ordem de tempo, cada um com as três classes. Essas
contagens valem para o dataset de 7 dias atual: se a coleta for refeita, as checagens falham
de propósito (ver `src/preditor/config.py`). O Gold também imprime os fluxos excluídos, a
contagem por classe e três exemplos reais (um OK, um RISCO e um FALHA) para o diário.

## Como o código está dividido

```text
src/preditor/
  config.py                parâmetros globais: tabela, corte A/B, piso, limiares da regra, horizonte do futuro, recorte e caminhos
  spark.py                 SparkSession local (o conector BigQuery só entra no bronze)
  __main__.py              Pipeline         escolhe a camada, orquestra, grava e verifica
  bronze/
    ingestao.py            Bronze           tabela do BigQuery → Parquet, como está
  silver/
    medicao.py             Medicoes         Bronze → 1 linha por medição (RTT, jitter, perda, período), sem duplicatas
  gold/
    calculo_x/
      baseline.py          Baseline         ficha por fluxo, só com o Período A
      features.py          Features         métricas relativas e janela das últimas 5 medições
      relatorio_regiao.py  RelatorioRegiao  limites em ms por região (derivado do baseline)
    calculo_y/
      rotulo.py            Rotulo           `regra`, `status_atual` (RFC §8.4) e `status_futuro` (3ª medição à frente)
      recorte.py           Recorte          `bloco`: treino / validação / teste por dois cortes de tempo globais
```

As fórmulas seguem a RFC (§8.2 a §8.4). O código comenta cada passo e não
repete a teoria.

## Decisões de implementação

As decisões abaixo foram tomadas sobre o dataset atual e ainda não estão nos documentos da pasta `docs/`:

- **Dataset de 7 dias, e não 14.** A tabela cobre 18/09 a 25/09/2026. O
  Período A são as primeiras **108 h**, o menor corte em que todos os fluxos
  passam de 1.500 RTT válidos. O Período B é o restante, cerca de 2,5 dias.
  As datas de corte citadas na RFC são de uma coleta anterior.
- **RTT válido** = ping com `rtt > 0` e `timeout = false`. No RIPE Atlas, o
  ping com timeout vem com `rtt = 0.0`.
- **RTT da medição** = média dos pings válidos da rajada (equivale ao campo
  `avg` do Atlas). **Jitter** = média de |Δrtt| entre pings consecutivos.
- **`fluxo_id` = `prb_id|dst_addr|msm_id`.** Separa as séries quando mais de
  uma medição do Atlas cobre o mesmo par. Com isso são 81 fluxos no baseline: 79
  com baseline e 2 marcados como `baseline_insuficiente`. Um 82º fluxo só tem
  medições no Período B e também fica fora do modelo (o Silver tem os 82).
- **Região e país são metadados**, não features: a RFC proíbe usá-los na
  árvore.
