# Preditor de falhas ML

Coleta de pings no RIPE Atlas. O **collector** é GET-only:
`fetch_measurement_results` lê `/measurements/{msm_id}/results/` de uma medição
já existente e devolve um DataFrame com o JSON bruto. A CLI `getResults` imprime
a tabela; `append_data` **acrescenta** as linhas em JSONL só se `--output-dir`
for passado.

`createPeriodic` (S1.6 / S1.8) cria as **8 medições periódicas** do hub (POST,
`is_oneoff: false`, `interval` 300, ping `packets=8`) para `94.140.14.14`
(AdGuard DNS, estável), `208.67.222.222` (OpenDNS, estável),
`202.12.28.131` (APNIC, caminho longo) e `4.2.2.1` (Level3/Lumen, médio /
RISCO). A intenção original (`8.8.8.8`, `1.1.1.1`, `202.12.27.33`) ficou
superseded-for-quota — retry só se a cota global liberar; não entram neste
POST. `stopPeriodic` para a série (`DELETE /measurements/{id}/`; histórico
GET permanece). `getData` é só um ping **one-off** de demo — não é a série
de treino. A Lambda da S1.7 **reutiliza** `fetch_measurement_results`; não
reimplementa HTTP nem chama `createPeriodic` / `get_data`.

O dataset de treino é o acumulado dos GETs desses 8 `msm_id`. O POST é só
setup. Detalhe e runbook: `docs/dataset-fonte-atlas.md`.

`features.py` (S1.3 / S2.1) é puro (sem HTTP/Path): `feature_row` extrai X;
`label_row` aplica `status_real` (perda > 15 → `FALHA`; senão latência > 100
→ `RISCO`; senão `OK`). A Lambda `preditor-falhas-collector` (S1.7) orquestra
GET + rótulo + S3 em `curated/features.csv` e `curated/labels.csv`. PingER não
está integrado. Sem treino ML neste incremento.

## Notebooks da disciplina

São a documentação pedida pela professora, **não** o pipeline de produção.
O core continua no pacote (`atlas.py` + CLI); a Lambda da S1.7 reutiliza o GET.

- `notebooks/01_coleta_atlas_raw.ipynb` (S1.2) — importa
  `fetch_measurement_results`, mostra o DataFrame bruto e, se quiser, chama
  `append_data` em `data/raw/`. Não reimplementa HTTP e não cria medição.
- `notebooks/02_post_medicoes_periodicas.ipynb` (S1.6) — importa
  `create_periodic_measurements`, `get_credits` e `write_measurement_ids`.
  Documenta o POST periódico (fonte do dataset). A célula ao vivo fica
  desligada (`CRIAR_MEDICOES = False`); sem chave, bloqueia e **não inventa**
  `msm_id`. Não usa `requests` nem `get_data` como série de treino.

## Ambiente

Requer Python 3.12 ou superior e uv. Na raiz do repositório:

```bash
uv sync
```

`requests` é a dependência HTTP. `pandas` é a tabela. `boto3` é o SDK de S3 e
Secrets Manager (já existe no runtime da Lambda; o zip de deploy **não** o
empacota). Ruff, Pyrefly e pytest são de desenvolvimento.

## Usar pelo terminal

Na raiz do repositório, com uv:

```bash
uv sync
uv run python -m preditor_de_falhas_ml
uv run python -m preditor_de_falhas_ml --help
uv run python -m preditor_de_falhas_ml getCredits --help
uv run python -m preditor_de_falhas_ml getResults --help
uv run python -m preditor_de_falhas_ml createPeriodic --help
uv run python -m preditor_de_falhas_ml stopPeriodic --help
uv run python -m preditor_de_falhas_ml getData --help
uv run python -m preditor_de_falhas_ml migrateCurated --help
```

Sem operação, ou com `--help`, mostra a ajuda e não acessa o Atlas.

**Chave:** `getCredits`, `getResults`, `createPeriodic`, `stopPeriodic` e
`getData` exigem `RIPE_ATLAS_API_KEY`. `migrateCurated` não — só S3.
Os exemplos Atlas abaixo carregam `.env` com uv; se a variável já estiver
no ambiente, remova `--env-file .env`.

```bash
uv run --env-file .env python -m preditor_de_falhas_ml getCredits
uv run --env-file .env python -m preditor_de_falhas_ml getResults --msm-id 12345 --start 1710000000 --stop 1710000900
uv run --env-file .env python -m preditor_de_falhas_ml getResults --msm-id 12345 --start 1710000000 --stop 1710000900 --output-dir data/raw
uv run --env-file .env python -m preditor_de_falhas_ml createPeriodic --ids-file data/msm_ids.json
uv run --env-file .env python -m preditor_de_falhas_ml stopPeriodic --ids-file data/msm_ids.json
uv run --env-file .env python -m preditor_de_falhas_ml getData
uv run --env-file .env python -m preditor_de_falhas_ml getData --target 8.8.8.8 --af 4 --country-code BR --probe-count 1 --packets 16 --output-dir data/raw
uv run python -m preditor_de_falhas_ml migrateCurated --bucket preditor-falhas-ml
```

`getResults` (collector) exige `--msm-id`, `--start` e `--stop` (unix). Faz um
GET na janela informada, imprime o DataFrame e **não** cria medição. Sem
`--output-dir` não grava arquivo; com `--output-dir`, `append_data` acrescenta
uma linha JSON por probe no JSONL.

`createPeriodic` (S1.6 / S1.8) **sempre cria** as 8 medições periódicas do
hub (consome créditos; corre até `stopPeriodic` / DELETE no Atlas). Consulta
créditos antes/depois, imprime os `msm_id` e a linha
`export RIPE_ATLAS_MSM_IDS=…`. Com `--ids-file`, grava JSON **sem a API
key** (o caminho em `data/` já é gitignorado). Com `--wait-seconds 300`,
espera um ciclo e GET em cada `msm_id` via `fetch_measurement_results`.
Não é o collector.

`stopPeriodic` envia `DELETE /measurements/{id}/` (stop documentado; HTTP
204; não apaga `/results/`). IDs vêm de `--ids-file` ou
`RIPE_ATLAS_MSM_IDS`. Atlas **não** reinicia medição Stopped — retomar é
outro `createPeriodic` (novos ids).

`migrateCurated` (S2.1) lê `curated/log_rede.csv` no S3, se existir, e
grava `curated/features.csv` + `curated/labels.csv` com a mesma chave
`(msm_id, timestamp, prb_id)`. Idempotente; no-op se o legado não existir.
Não pede `RIPE_ATLAS_API_KEY` e **não** retoma Atlas/EventBridge. Runbook:
`docs/migracao_curated_xy.md`.

`getData` (demo one-off: `8.8.8.8`, IPv4, 16 pacotes, 1 probe no Brasil)
**sempre cria** uma medição nova (consome créditos). Depois do POST, consulta
os resultados via `fetch_measurement_results`, imprime o DataFrame e grava
**uma linha JSON por probe** em `data/raw/measurements.jsonl`. Uma segunda
execução não apaga a primeira. Se o ping ainda não terminou, espera alguns
segundos e tenta o GET de novo. Não usar para a série de treino.

Cada linha é um objeto do array de `GET /results/`:

```json
{"msm_id": 12345, "prb_id": 9, "type": "ping", "result": [{"rtt": 12.3}]}
```

O JSON não é interpretado (sem latência/perda/jitter/`status_real` derivados).
Falhas de HTTP ou de chave sobem como exceção do `requests` (sem envelope
próprio).

## Usar em código

```python
import os
from pathlib import Path

from preditor_de_falhas_ml import (
    append_data,
    create_periodic_measurements,
    feature_row,
    fetch_measurement_results,
    get_credits,
    get_data,
    label_row,
    status_real,
)

key = os.environ["RIPE_ATLAS_API_KEY"]
print(get_credits(key))
frame = fetch_measurement_results(key, 12345, start=1710000000, stop=1710000900)
append_data(frame, output_dir=Path("data/raw"))
# feature_row(record) / label_row(features) / status_real(perda, latencia)
# create_periodic_measurements(key) — POST setup (S1.6), não o collector
# get_data(key) cria medição one-off — não usar no collector nem no dataset
```

Runbook da Lambda: `docs/aws_lambda.md`.

## Estrutura

```text
src/preditor_de_falhas_ml/
  atlas.py      GET /credits/, POST periódico / DELETE stop / one-off, GET /results/, JSONL
  features.py   S1.3/S2.1: feature_row (X) + label_row / status_real (Y); puro
  collector.py  S1.7/S2.1: GET + rótulo + I/O S3 features.csv/labels.csv (sem POST)
  handler.py    Lambda preditor-falhas-collector
  cli.py        getCredits, getResults, createPeriodic, stopPeriodic, getData, migrateCurated
infra/aws/      package.sh, deploy.sh, invoke.sh, verify.sh
infra/cloudformation/s1-secrets-iam-s3.yaml   stack preditor-falhas-s1
docs/aws_lambda.md                           runbook S1.7 + kill-switch
docs/aws_s3.md                               layout raw + features/labels (S2.1)
docs/migracao_curated_xy.md                  log_rede.csv → features + labels
docs/dataset-fonte-atlas.md                  S1.6: POST = setup; dataset = GETs
```

Contrato para o próximo incremento: `AGENTS.md`.

## Validação

Comandos executados neste incremento:

```bash
uv sync
uv run ruff format .
uv run ruff check .
uv run pyrefly check
uv run pytest
```

Os testes simulam `requests.request`. O POST ao vivo das 8 medições usa
`RIPE_ATLAS_API_KEY` (nunca commitada). IDs reais e saldo: `docs/dataset-fonte-atlas.md`.
Sem treino de modelo.

## Fora deste incremento

- Tratamento de erro HTTP
- Treino da árvore / Streamlit
- Fonte PingER
- Compartilhar a API key da Lambda com o time

## Referências

- [Autenticação com chave de API](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/api-keys/)
- [Consulta de créditos](https://atlas.ripe.net/docs/apis/rest-api-reference/credits/credits_retrieve)
- [Criação de medições](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/)
- [Atualizar e parar medições](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/updating-and-stopping/)
- [Seleção de probes](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/probe-selection/)
- [Resultados de medições](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results)
- [Formato dos resultados de ping](https://atlas.ripe.net/docs/apis/measurement-result-format/version-5000#version-5000-ping-v6-ping)
