# Preditor de falhas ML

Pipeline Python para a equipe coletar pings no RIPE Atlas e montar
`X = [latência, perda, jitter]` por probe e instante. A CLI cria a medição
(alvo, família, probes, intervalo e duração configuráveis), consulta resultados
e grava um dataset local. O default da criação continua ping IPv4 pontual para
**8.8.8.8**.

Não há rótulo de falha nem treino ML neste incremento. PingER não está integrado.

## Ambiente

Requer Python 3.12 ou superior e uv. Na raiz do repositório:

```bash
uv sync
```

`requests` é a dependência HTTP. Ruff e pytest são de desenvolvimento.

## Usar pelo terminal

```bash
uv run python -m preditor_de_falhas_ml
uv run python -m preditor_de_falhas_ml --help
```

Sem argumentos, mostra a ajuda e não acessa o Atlas.

**Chave:** `create-sample` e `credits` exigem `RIPE_ATLAS_API_KEY`.
`results`, `features` e `dataset collect` consultam endpoints públicos sem chave.
Os exemplos abaixo carregam `.env` com uv; se a variável já estiver no ambiente,
remova `--env-file .env`.

Consultar créditos:

```bash
uv run --env-file .env python -m preditor_de_falhas_ml credits
```

Criar um ping (default: `8.8.8.8`, IPv4, one-off, 16 pacotes, 1 probe do país):

```bash
uv run --env-file .env python -m preditor_de_falhas_ml create-sample --country-code BR --probe-count 2 --packets 4
uv run --env-file .env python -m preditor_de_falhas_ml create-sample --country-code BR --target 1.1.1.1 --af 4 --interval 300 --duration 3600
```

`--interval` e `--duration` vêm juntos (medição recorrente) ou os dois ausentes
(one-off). A criação consome créditos e imprime `ID da medição: <id>`.

Consultar resultados brutos e calcular X (chave opcional):

```bash
uv run python -m preditor_de_falhas_ml results 12345
uv run python -m preditor_de_falhas_ml features 12345 --probe-id 1000173 --start 1788800000 --stop 1788900000
uv run python -m preditor_de_falhas_ml dataset collect 12345 67890 --output-dir data
uv run python -m preditor_de_falhas_ml dataset rebuild --output-dir data
```

`--probe-id`, `--start` e `--stop` filtram a consulta de resultados. O programa
não espera a medição terminar. `[]` é válido. Dataset schema **v2**: histórico
em `raw.jsonl`, CSV em `dataset.csv`. Diretórios com schema v1 não são migrados;
use outro `--output-dir`.

Saídas normais vão para `stdout`; erros para `stderr`, sem traceback ou chave.
Código 0 em sucesso/ajuda, 1 em falha operacional, 2 em sintaxe inválida.

## Usar em código

A fachada pública são os use cases, não o cliente HTTP:

```python
import os

from preditor_de_falhas_ml import (
    MeasurementSpec,
    collect_measurement,
    create_measurement,
)
from preditor_de_falhas_ml.adapters.atlas import AtlasGateway
from preditor_de_falhas_ml.adapters.file_dataset import FileDataset
from preditor_de_falhas_ml.domain.ids import MeasurementId
from preditor_de_falhas_ml.domain.spec import CountrySelection

store = FileDataset("data")
store.prepare()
spec = MeasurementSpec(
    target="8.8.8.8",
    address_family=4,
    selection=CountrySelection("BR", 1),
    packets=16,
)
with AtlasGateway(os.environ["RIPE_ATLAS_API_KEY"]) as atlas:
    measurement_id = create_measurement(atlas, store, spec)
    report = collect_measurement(atlas, store, measurement_id)
X = [
    [row.features.latency_ms, row.features.loss_pct, row.features.jitter_rtt_ms]
    for row in report.observations
]
```

Consultas públicas: `AtlasGateway(None)`. Criação e créditos exigem chave.
A chave tem prioridade sobre `.netrc`. Proxy e certificados do ambiente
continuam valendo.

## X e dados ausentes

| Atributo | Definição |
| --- | --- |
| `latency_ms` | Média dos RTTs sem duplicatas, em ms. |
| `loss_pct` | `100 * (sent - rcvd) / sent`. |
| `jitter_rtt_ms` | Média de `abs(RTT seguinte - RTT anterior)` nos pares consecutivos com resposta. |

Timeout e erro de pacote não entram na latência e quebram o par do jitter.
Sem respostas, latência e jitter são `null`; perda 100% se houve envio.
Observação identificável por `(msm_id, prb_id, timestamp)` permanece no CSV
mesmo incompleta (`quality=incomplete`, X nulo). Só vai para `rejected.jsonl`
o resultado sem essa chave. Colunas extras (min/max/mediana/desvio/streak)
são diagnóstico, não X.

Na medição **209319472** (08/09/2026):

| Probe | Latência (ms) | Perda (%) | Jitter de RTT (ms) |
| --- | ---: | ---: | ---: |
| 1000173 | 19,425243 | 0 | 0,069196 |
| 1016739 | 3,356288 | 0 | 0,610702 |

## Estrutura (vale para o que vier)

O projeto segue Clean Architecture em três camadas. **Qualquer** capacidade
nova (rótulo de falha, modelo, PingER, S3, outro provedor) entra nessas pastas,
não como módulo solto na raiz do pacote:

```text
src/preditor_de_falhas_ml/
  domain/         regra pura (X, futuras entidades de falha/modelo)
  application/    use cases e ports (create, collect, futuros treino/rótulo)
  adapters/       drivers: Atlas HTTP, arquivos, CLI; depois S3/PingER/ML
```

Fluxo de todo comando: argumentos e ambiente na CLI → use case → port
(gateway/dataset/…) → JSON ou erro. A equipe usa a CLI; código Python chama
use cases. O cliente HTTP não é a fachada.

Contrato para quem for implementar o próximo incremento: `AGENTS.md`.
Como encaixar tipo, port ou pasta: `docs/organizacao.md`.

## Validação

Comandos executados neste incremento:

```bash
uv sync
uv run ruff format .
uv run ruff check .
uv run pytest
```

Resultado: formatter sem diff, lint exit 0, 98 testes. Os use cases rodam com
fakes in-memory (sem `requests` e sem filesystem). Os adapters HTTP usam
`Session.send` simulado. A CLI cobre chave opcional, `--target`/`--interval`/
`--duration`, JSON bruto e erros sem traceback.

Este incremento não cria medição nova na API real nem treina modelo.

## Fora deste incremento

- Rotulagem de falha e treino ML
- Fonte PingER
- Polling até a medição terminar
- Migração automática de `data/` schema v1
- Gravação no Amazon S3

## Referências

- [Autenticação com chave de API](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/api-keys/)
- [Consulta de créditos](https://atlas.ripe.net/docs/apis/rest-api-reference/credits/credits_retrieve)
- [Criação de medições](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/)
- [Seleção de probes](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/probe-selection/)
- [Resultados de medições](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results)
- [Formato dos resultados de ping](https://atlas.ripe.net/docs/apis/measurement-result-format/version-5000#version-5000-ping-v6-ping)
