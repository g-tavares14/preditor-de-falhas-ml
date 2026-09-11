# Preditor de falhas ML

Coleta de pings no RIPE Atlas. O **collector** é GET-only:
`fetch_measurement_results` lê `/measurements/{msm_id}/results/` de uma medição
já existente e devolve um DataFrame com o JSON bruto. A CLI `getResults` imprime
a tabela; `append_data` **acrescenta** as linhas em JSONL só se `--output-dir`
for passado.

`getData` **não** é o collector: cria uma medição one-off (POST, consome
créditos) — caminho de setup (S1.6). A Lambda da S1.7 **reutiliza**
`fetch_measurement_results`; não reimplementa HTTP nem chama `get_data`.

Não há rótulo de falha nem treino ML neste incremento. PingER não está integrado.

## Ambiente

Requer Python 3.12 ou superior e uv. Na raiz do repositório:

```bash
uv sync
```

`requests` é a dependência HTTP. `pandas` é a tabela. Ruff, Pyrefly e pytest
são de desenvolvimento.

## Usar pelo terminal

Na raiz do repositório, com uv:

```bash
uv sync
uv run python -m preditor_de_falhas_ml
uv run python -m preditor_de_falhas_ml --help
uv run python -m preditor_de_falhas_ml getCredits --help
uv run python -m preditor_de_falhas_ml getResults --help
uv run python -m preditor_de_falhas_ml getData --help
```

Sem operação, ou com `--help`, mostra a ajuda e não acessa o Atlas.

**Chave:** `getCredits`, `getResults` e `getData` exigem `RIPE_ATLAS_API_KEY`.
Os exemplos abaixo carregam `.env` com uv; se a variável já estiver no ambiente,
remova `--env-file .env`.

```bash
uv run --env-file .env python -m preditor_de_falhas_ml getCredits
uv run --env-file .env python -m preditor_de_falhas_ml getResults --msm-id 12345 --start 1710000000 --stop 1710000900
uv run --env-file .env python -m preditor_de_falhas_ml getResults --msm-id 12345 --start 1710000000 --stop 1710000900 --output-dir data/raw
uv run --env-file .env python -m preditor_de_falhas_ml getData
uv run --env-file .env python -m preditor_de_falhas_ml getData --target 8.8.8.8 --af 4 --country-code BR --probe-count 1 --packets 16 --output-dir data/raw
```

`getResults` (collector) exige `--msm-id`, `--start` e `--stop` (unix). Faz um
GET na janela informada, imprime o DataFrame e **não** cria medição. Sem
`--output-dir` não grava arquivo; com `--output-dir`, `append_data` acrescenta
uma linha JSON por probe no JSONL.

`getData` (S1.6, default: `8.8.8.8`, IPv4, 16 pacotes, 1 probe no Brasil)
**sempre cria** uma medição nova (consome créditos). Depois do POST, consulta
os resultados via `fetch_measurement_results`, imprime o DataFrame e grava
**uma linha JSON por probe** em `data/raw/measurements.jsonl`. Uma segunda
execução não apaga a primeira. Se o ping ainda não terminou, espera alguns
segundos e tenta o GET de novo.

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
    fetch_measurement_results,
    get_credits,
    get_data,
)

key = os.environ["RIPE_ATLAS_API_KEY"]
print(get_credits(key))
frame = fetch_measurement_results(key, 12345, start=1710000000, stop=1710000900)
append_data(frame, output_dir=Path("data/raw"))
# get_data(key) cria medição (POST) — não usar no collector
```

## Estrutura

```text
src/preditor_de_falhas_ml/
  atlas.py   GET /credits/, POST /measurements/, GET /results/, append do JSONL
  cli.py     argparse: getCredits, getResults (GET) e getData (POST)
tests/       HTTP simulado (requests.request) e CLI getResults
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

Os testes simulam `requests.request`. Este incremento não cria medição na API
real nem treina modelo.

## Fora deste incremento

- Tratamento de erro HTTP
- Rotulagem de falha e treino ML
- Cálculo de `latency_ms`, `loss_pct`, `jitter_rtt_ms` / `status_real`
- Fonte PingER
- Medição recorrente (`interval` / `duration`) — S1.6
- Lambda e gravação no Amazon S3 — S1.7 reutiliza `fetch_measurement_results`

## Referências

- [Autenticação com chave de API](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/api-keys/)
- [Consulta de créditos](https://atlas.ripe.net/docs/apis/rest-api-reference/credits/credits_retrieve)
- [Criação de medições](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/)
- [Seleção de probes](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/probe-selection/)
- [Resultados de medições](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results)
- [Formato dos resultados de ping](https://atlas.ripe.net/docs/apis/measurement-result-format/version-5000#version-5000-ping-v6-ping)
