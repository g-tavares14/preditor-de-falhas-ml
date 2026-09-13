# Fonte do dataset de treino (S1.6 / S1.8)

O dataset de treino **não** é o payload do POST. O POST só **aponta** as
medições periódicas. O histórico que treina o modelo é o **acumulado dos GETs**
em `fetch_measurement_results` / CLI `getResults` (local e, depois, Lambda S1.7)
sobre os 8 `msm_id` abaixo.

```text
POST createPeriodic (uma vez / ao reconfigurar)
  → 8 msm_id periódicos (fonte)
GET getResults (sempre: local + Lambda)
  → raw JSONL → curated/log_rede.csv
  → dataset de treino
```

O collector agendado **não** chama `createPeriodic` nem `getData`. Runbook
Lambda: `docs/aws_lambda.md`. IDs Stopped: `210717688`–`210717693` (S1.6).
Série 900s/6 msm (S1.7) `210732689,210732690,210732692,210732693,210732696,210732697`
foi **recriada** na S1.8 (stop + POST novo; ver Tentativa 4). EventBridge
continua `rate(15 minutes)` — só o intervalo Atlas mudou (900→300).

Documentação da disciplina (não é o collector):
`notebooks/02_post_medicoes_periodicas.ipynb`.

## Matriz do hub (fixa)

| Destino | Papel | Tipo | Pacotes | Probes | Intervalo |
|---|---|---|---|---|---|
| 94.140.14.14 (AdGuard DNS) | estável | ping | 8 | 2 BR | 300 s |
| 94.140.14.14 (AdGuard DNS) | estável | traceroute ICMP | 3 | 2 BR | 300 s |
| 208.67.222.222 (OpenDNS) | estável | ping | 8 | 2 BR | 300 s |
| 208.67.222.222 (OpenDNS) | estável | traceroute ICMP | 3 | 2 BR | 300 s |
| 202.12.28.131 (APNIC) | caminho longo | ping | 8 | 2 BR | 300 s |
| 202.12.28.131 (APNIC) | caminho longo | traceroute ICMP | 3 | 2 BR | 300 s |
| 4.2.2.1 (Level3/Lumen) | médio | ping | 8 | 2 BR | 300 s |
| 4.2.2.1 (Level3/Lumen) | médio | traceroute ICMP | 3 | 2 BR | 300 s |

Intenção original (superseded-for-quota; **não** entra neste POST):
`8.8.8.8`, `1.1.1.1`, `202.12.27.33`. A primeira tentativa ao vivo
(2026-09-11) foi rejeitada pela cota global em `8.8.8.8`. Retry dessa
matriz só se a cota global liberar.

`is_oneoff: false`. One-off (`getData`) custa mais e **não** serve para a série
de treino.

O 4º hub (`4.2.2.1`) existe para o curated gerar **RISCO** sem mudar o limiar
`status_real` (perda > 15 → FALHA; senão latência > 100 → RISCO; senão OK).
AdGuard/OpenDNS continuam o papel estável (OK); APNIC o caminho longo (FALHA).
Volume S1.8: intervalo 900→300 s e ping 5→8 pacotes em **todas** as 8 msm
(recreate, não só no hub novo).

As medições periódicas **continuam cobrando créditos** enquanto estão
Scheduled/Ongoing. Com 8 msm + ping 8 + 300 s o burn sobe ~linear; headroom
~100k ainda cobre. Monitorar saldo após o 1º lote Atlas (4–6 h). A série
900s/6 msm da S1.7 foi parada no recreate S1.8 — ver Tentativa 4.

## Persistência dos msm_id (sem a API key)

A chave fica só em `RIPE_ATLAS_API_KEY` (`.env` gitignorado, Secret ou SSM).
Os IDs **não** são a chave; podem ir para env/Secret e, depois do POST ao vivo,
para esta página.

- Arquivo local (gitignorado em `data/`): `--ids-file data/msm_ids.json`
- Env / Secret para o collector: `RIPE_ATLAS_MSM_IDS=id1,id2,…,id8`
  (a CLI imprime a linha `export …` após o POST)

Não commitar `.env` nem a API key.

## Runbook — POST ao vivo

Requer `RIPE_ATLAS_API_KEY` com permissão de **create**. Sem a chave, o POST
real fica bloqueado; não inventar `msm_id`.

```bash
uv sync
uv run --env-file .env python -m preditor_de_falhas_ml getCredits
uv run --env-file .env python -m preditor_de_falhas_ml createPeriodic \
  --ids-file data/msm_ids.json
```

O comando consulta créditos antes e depois, faz **um** POST com as 8 definições
e imprime os `msm_id`. Para validar 1 ciclo (~5 min) no mesmo processo:

```bash
uv run --env-file .env python -m preditor_de_falhas_ml createPeriodic \
  --ids-file data/msm_ids.json \
  --wait-seconds 300
```

`--wait-seconds` só espera e chama o GET já existente
(`fetch_measurement_results`). Não cria outra medição.

Validação posterior (collector), um `msm_id` por vez:

```bash
uv run --env-file .env python -m preditor_de_falhas_ml getResults \
  --msm-id MSM_ID --start UNIX --stop UNIX
```

Copiar os 8 IDs e os saldos para a tabela abaixo. O primeiro ciclo pode ainda
estar vazio se as probes BR não tiverem reportado; repetir o GET.

## Runbook — parar a série (stop)

`DELETE /api/v2/measurements/{id}/` é o stop documentado do Atlas
([Updating and Stopping](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/updating-and-stopping/),
[measurements_destroy](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_destroy)):
HTTP 204, sem corpo. **Não apaga** o histórico — `GET /results/` continua.

Não há restart. Medição Stopped fica Stopped (pode ir a Archived). Para
retomar a série: `createPeriodic` de novo — **novos** `msm_id`. Não reutilizar
os IDs parados como se voltassem a emitir.

```bash
uv run --env-file .env python -m preditor_de_falhas_ml stopPeriodic \
  --ids-file data/msm_ids.json
# ou: RIPE_ATLAS_MSM_IDS=id1,id2,id3,id4,id5,id6,id7,id8
uv run --env-file .env python -m preditor_de_falhas_ml stopPeriodic
```

Depois do recreate S1.8, atualizar o env da Lambda (este agente **não** tem
AWS CLI neste ambiente):

```bash
aws lambda update-function-configuration \
  --function-name preditor-falhas-collector \
  --region sa-east-1 \
  --environment "Variables={S3_BUCKET=preditor-falhas-ml,RIPE_ATLAS_MSM_IDS=ID1,ID2,ID3,ID4,ID5,ID6,ID7,ID8,SECRET_NAME=RIPE_ATLAS_API_KEY,COLLECT_WINDOW_SECONDS=1200}"
```

Ou `./infra/aws/deploy.sh` com `RIPE_ATLAS_MSM_IDS` exportado. Não inventar IDs.
EventBridge `preditor-falhas-collector-15min` permanece ENABLED; a cadência
Lambda não muda.

## Piloto one-off S1.8 (escolher o hub médio)

One-off ping, 2 probes BR, 8 pacotes, IPv4. Créditos 100000→100000 no instante.
Nenhum limiar `status_real` foi alterado. Candidatos saturados (`8.8.8.8` /
`1.1.1.1`) não foram POSTados.

| Destino | Papel no piloto | msm_id | prb_id | RTT médio (ms) | RTT mediana (ms) | Perda | Faixa 100–200 ms e perda ≤15% |
|---|---|---|---|---|---|---|---|
| 9.9.9.9 (Quad9) | anycast / candidato 1 | 210928315 | 1015587, — | 3.5 / 21.1 | 21.1 | 0% | não (OK, ~3–21 ms) |
| 89.233.43.71 (UncensoredDNS unicast DK) | europeu unicast | 210928319 | 1000709, 1002873 | 220.1 | 222.0 | 0% | não (acima de 200 ms) |
| 84.200.69.80 (DNS.WATCH DE) | europeu / pouco anycast | 210928322 | 1002873, 1014381 | 215.2 | 223.6 | 0% | não (acima de 200 ms) |
| 4.2.2.1 (Level3/Lumen) | terceiro (1º e 2º fora da faixa) | 210928514 | 1000489, 1008715 | 147.3 | 176.3 | 0% | **sim** (118 e 176 ms) |
| 80.58.61.250 (Telefonica ES) | extra ibérico | 210928522 | 1009598, 1016740 | — | — | 100% | não (FALHA) |

**Escolhido:** `4.2.2.1` (Level3/Lumen). Cota pública no POST: 0 ping ativos
nesse alvo. Os dois europeus gerariam RISCO (RTT > 100 e perda 0), mas
ficaram fora da faixa pedida (100–200 ms).

## Registro do POST ao vivo

### Tentativa 4 — S1.8 hub médio + volume (300 s / ping 8 / 8 msm)

**Estado:** recreate **pendente neste PR** (código/docs já na matriz nova).
Plano: `stopPeriodic` das 6 Ongoing 900s
(`210732689,210732690,210732692,210732693,210732696,210732697`) e
`createPeriodic` das 8 definições (AdGuard / OpenDNS / APNIC / Level3).
Sem overlap longo: stop primeiro, POST em seguida. Collector GET nas
antigas continua a ler histórico; linhas novas só após o Secret/env
receber os 8 IDs.

| Campo | Valor |
|---|---|
| Créditos antes | *pendente recreate* |
| Créditos depois | *pendente recreate* |
| Matriz enviada | 94.140.14.14, 208.67.222.222, 202.12.28.131, 4.2.2.1 × ping + traceroute ICMP; `is_oneoff: false`; interval 300; ping 8; tr 3; 2 probes BR |
| `export RIPE_ATLAS_MSM_IDS` | *pendente recreate — não inventar IDs* |
| AWS Secret / Lambda env | **follow-up:** este ambiente não tem AWS CLI; copiar a linha `export` para `RIPE_ATLAS_MSM_IDS` |

### Tentativa 3 — retomar série após collector S1.7

**Estado:** POST ao vivo **aceitou** (2026-09-12, ~00:30 UTC). Hub inalterado
(AdGuard / OpenDNS / APNIC). Um POST com as 6 definições; `data/msm_ids.json`
gravado **sem** a API key (gitignorado). A chave estava presente
(`RIPE_ATLAS_API_KEY` present=true, length=36; valor não registrado).
O collector **não** chama este POST. IDs novos foram para o env da Lambda
`RIPE_ATLAS_MSM_IDS` (não os Stopped). Invoke com os IDs novos: HTTP 200,
janela vazia (probes ainda não reportaram). EventBridge
`preditor-falhas-collector-15min` **ENABLED** depois desse invoke.

| Campo | Valor |
|---|---|
| Créditos antes | 100000 |
| Créditos depois | 100000 |
| Delta | 0 no instante (cobrança periódica começa com a série Ongoing) |
| Matriz enviada | 94.140.14.14, 208.67.222.222, 202.12.28.131 × ping + traceroute ICMP; `is_oneoff: false`; interval 900; 2 probes BR |
| Status Atlas no POST | Scheduled/Ongoing (6 IDs devolvidos) |
| EventBridge | `preditor-falhas-collector-15min` **ENABLED** (após invoke com IDs novos; janela vazia OK) |
| Lambda ARN | `arn:aws:lambda:sa-east-1:274394226829:function:preditor-falhas-collector` |
| `export RIPE_ATLAS_MSM_IDS` | `210732689,210732690,210732692,210732693,210732696,210732697` |

| msm_id | Destino | Tipo | Papel | prb_id (1º ciclo) | timestamps | créditos antes | créditos depois |
|---|---|---|---|---|---|---|---|
| 210732689 | 94.140.14.14 | ping | estável | — | POST 2026-09-12 ~00:30 UTC | 100000 | 100000 |
| 210732690 | 94.140.14.14 | traceroute ICMP | estável | — | POST 2026-09-12 ~00:30 UTC | 100000 | 100000 |
| 210732692 | 208.67.222.222 | ping | estável | — | POST 2026-09-12 ~00:30 UTC | 100000 | 100000 |
| 210732693 | 208.67.222.222 | traceroute ICMP | estável | — | POST 2026-09-12 ~00:30 UTC | 100000 | 100000 |
| 210732696 | 202.12.28.131 | ping | caminho longo | — | POST 2026-09-12 ~00:30 UTC | 100000 | 100000 |
| 210732697 | 202.12.28.131 | traceroute ICMP | caminho longo | — | POST 2026-09-12 ~00:30 UTC | 100000 | 100000 |

### Tentativa 2 — nova matriz (desbloqueio de cota)

**Estado:** POST ao vivo **aceitou** (2026-09-11, ~22:45 UTC). Série **pausada**
em 2026-09-11, ~23:03 UTC, pending Lambda S1.7 — as 6 medições estavam
`Ongoing` e cobrariam créditos sem collector GET/S3. A chave estava presente
(`RIPE_ATLAS_API_KEY` present=true, length=36; valor não registrado nem
commitado). Um POST com as 6 definições; `data/msm_ids.json` gravado **sem**
a API key (gitignorado). GET imediato em `210717688` devolveu DataFrame
vazio — medições ainda `Scheduled`. `--wait-seconds 900` **não** rodou.
O collector **não** chama este POST.

Stop ao vivo: `DELETE /api/v2/measurements/{id}/` (6/6 HTTP 204). GET
metadados depois: `Stopped` (status id 4). `GET /results/` em `210717688`
ainda devolveu 2 linhas — histórico intacto. Atlas **não** reinicia medição
parada; retomar = `createPeriodic` (novos ids). Sem IDs inventados. Sem
mudança em `HUB_SPECS`.

| Campo | Valor |
|---|---|
| Créditos antes (POST) | 100000 |
| Créditos depois (POST) | 100000 |
| Créditos no stop | 100000 → 100000 (delta 0 no instante; cobrança periódica **encerra** ao Stopped) |
| Matriz enviada | 94.140.14.14, 208.67.222.222, 202.12.28.131 × ping + traceroute ICMP; `is_oneoff: false`; interval 900; 2 probes BR |
| Status Atlas no POST | Scheduled (6/6) |
| Status Atlas no stop (2026-09-11 ~23:03 UTC) | Stopped (6/6); `when` 1789167830–1789167832 |
| Endpoint de stop | `DELETE /api/v2/measurements/{id}/` (docs Atlas: stop, HTTP 204) |
| Retomar | `createPeriodic` de novo (novos msm_id). Sem restart no Atlas. |
| `export RIPE_ATLAS_MSM_IDS` | `210717688,210717689,210717690,210717691,210717692,210717693` (Stopped; não emitem mais) |

| msm_id | Destino | Tipo | Papel | prb_id (1º ciclo) | timestamps | créditos antes | créditos depois |
|---|---|---|---|---|---|---|---|
| 210717688 | 94.140.14.14 | ping | estável | — | Stopped 2026-09-11 23:03:50 UTC | 100000 | 100000 |
| 210717689 | 94.140.14.14 | traceroute ICMP | estável | — | Stopped 2026-09-11 23:03:50 UTC | 100000 | 100000 |
| 210717690 | 208.67.222.222 | ping | estável | — | Stopped 2026-09-11 23:03:51 UTC | 100000 | 100000 |
| 210717691 | 208.67.222.222 | traceroute ICMP | estável | — | Stopped 2026-09-11 23:03:51 UTC | 100000 | 100000 |
| 210717692 | 202.12.28.131 | ping | caminho longo | — | Stopped 2026-09-11 23:03:52 UTC | 100000 | 100000 |
| 210717693 | 202.12.28.131 | traceroute ICMP | caminho longo | — | Stopped 2026-09-11 23:03:52 UTC | 100000 | 100000 |

### Tentativa 1 — intenção original (superseded-for-quota)

POST ao vivo **não concluiu**. A chave estava presente no ambiente
do agente (`RIPE_ATLAS_API_KEY` present=true, length=36; valor não registrado).
`createPeriodic` foi executado **duas vezes** (2026-09-11, ~22:12 UTC). As duas
chamadas receberam HTTP 400 / code 102 do Atlas:

`We do not allow more than 25 concurrent measurements to the same target: 8.8.8.8.`

Nenhum `msm_id` foi inventado. `data/msm_ids.json` **não** foi gravado.

| Campo | Valor |
|---|---|
| Créditos antes | 100000 |
| Créditos depois | 100000 |
| Delta | 0 (POST rejeitado; sem cobrança) |
| Matriz enviada | 8.8.8.8, 1.1.1.1, 202.12.27.33 × ping + traceroute ICMP; `is_oneoff: false`; interval 900; 2 probes BR |

Contagem pública no momento da tentativa (`status` specified/scheduled/ongoing):

| Destino | Ativas (todos os tipos) | Periodic ping | Periodic traceroute |
|---|---|---|---|
| 8.8.8.8 | 30 | 16 | 5 |
| 1.1.1.1 | 30 | 13 | 9 |
| 202.12.27.33 | 33 | 0 | 1 |

A cota documentada pelo Atlas é “até 25 periódicas e 25 one-off **do mesmo
tipo** no mesmo destino”. O erro devolvido fala em 25 concorrentes **no
destino** (sem filtrar tipo). 8.8.8.8 tinha 30 medições ativas no total.
Relistar `/measurements/my/` com esta chave devolveu 403 (a chave
cria/consulta créditos, mas não lista “minhas” medições).

Medições públicas já existentes com descrição “Preditor de falhas ML” são só
três one-off ping a 8.8.8.8, todas `Stopped` — não são a série periódica do
hub e **não** entram na tabela.

| msm_id | Destino | Tipo | Papel | prb_id (1º ciclo) | timestamps | créditos antes | créditos depois |
|---|---|---|---|---|---|---|---|
| *pendente* | 8.8.8.8 | ping | estável | — | POST 400 | 100000 | 100000 |
| *pendente* | 8.8.8.8 | traceroute ICMP | estável | — | POST 400 | 100000 | 100000 |
| *pendente* | 1.1.1.1 | ping | estável | — | POST 400 | 100000 | 100000 |
| *pendente* | 1.1.1.1 | traceroute ICMP | estável | — | POST 400 | 100000 | 100000 |
| *pendente* | 202.12.27.33 | ping | caminho longo | — | POST 400 | 100000 | 100000 |
| *pendente* | 202.12.27.33 | traceroute ICMP | caminho longo | — | POST 400 | 100000 | 100000 |

Retry desta matriz original só se a cota global liberar. A matriz **atual**
do POST é a tentativa 4 (AdGuard / OpenDNS / APNIC / Level3 `4.2.2.1`).
