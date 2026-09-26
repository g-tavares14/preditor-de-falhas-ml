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
| `docs/data/processed/` | Saídas do pipeline (ignoradas pelo git) |

## Ambiente

Pré-requisitos:

- [uv](https://docs.astral.sh/uv/): gerencia Python 3.11 e as dependências (`pyspark` 3.5).
- **Java 17**, exigido pelo Spark:

  ```bash
  brew install openjdk@17
  echo 'export JAVA_HOME=/opt/homebrew/opt/openjdk@17' >> ~/.zshrc
  ```

- **gcloud autenticado**: o conector do BigQuery usa as credenciais padrão, sem
  arquivo de chave.

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

```bash
uv run python -m preditor
```

Na primeira execução o Spark baixa o conector do BigQuery, o que leva alguns
minutos. O pipeline lê `atlas-ripe-509700.atlasRipe.atlas` (região EU) e grava:

| Arquivo | Uma linha por | Conteúdo |
|---|---|---|
| `baseline_por_fluxo.parquet` | fluxo | Ficha do Período A: mediana, MAD, IQR, jitter e perda típicos, taxa de resposta, `baseline_insuficiente` |
| `features_B.parquet` | medição do Período B | O **X** do modelo: `latencia_relativa`, `aumento_pct`, `z_robusto`, `jitter_relativo`, `n5_*`, `tendencia`, `persistencia` |
| `limites_por_regiao.csv` | rota / país | Os limiares da regra traduzidos para ms, por região (só para leitura) |

No fim, o pipeline faz checagens automáticas: o Período A não pode vazar para
as features e nenhum timeout (`rtt = 0`) pode entrar como RTT válido. Também
imprime os fluxos excluídos.

## Como o código está dividido

```text
src/preditor/
  config.py            parâmetros: tabela, corte A/B, piso, limiares da regra
  spark.py             SparkSession local com o conector BigQuery
  medicao.py           Medicoes         tabela bruta → 1 linha por medição (RTT, jitter, perda, período)
  baseline.py          Baseline         ficha por fluxo, só com o Período A
  features.py          Features         métricas relativas e janela das últimas 5 medições
  relatorio_regiao.py  RelatorioRegiao  limites em ms por região
  __main__.py          Pipeline         orquestra, grava e verifica
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
  uma medição do Atlas cobre o mesmo par. Com isso são 81 fluxos: 79 com
  baseline e 2 marcados como `baseline_insuficiente`. Um terceiro fluxo só tem
  medições no Período B e também fica fora do modelo.
- **Região e país são metadados**, não features: a RFC proíbe usá-los na
  árvore.
