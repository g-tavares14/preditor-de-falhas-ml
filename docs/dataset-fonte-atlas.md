# Fonte do dataset de treino (S1.6)

O dataset de treino **não** é o payload do POST. O POST só **aponta** as
medições periódicas. O histórico que treina o modelo é o **acumulado dos GETs**
em `fetch_measurement_results` / CLI `getResults` (local e, depois, Lambda S1.7)
sobre os 6 `msm_id` abaixo.

```text
POST createPeriodic (uma vez / ao reconfigurar)
  → 6 msm_id periódicos (fonte)
GET getResults (sempre: local + Lambda)
  → raw JSONL → curated/log_rede.csv
  → dataset de treino
```

O collector agendado **não** chama `createPeriodic` nem `getData`. Runbook
Lambda: `docs/aws_lambda.md`. Os IDs `210717688`–`210717693` estão **Stopped**;
retomar a série = outro `createPeriodic` (novos ids) **antes** de ligar o
EventBridge.

Documentação da disciplina (não é o collector):
`notebooks/02_post_medicoes_periodicas.ipynb`.

## Matriz do hub (fixa)

| Destino | Papel | Tipo | Pacotes | Probes | Intervalo |
|---|---|---|---|---|---|
| 94.140.14.14 (AdGuard DNS) | estável | ping | 5 | 2 BR | 900 s |
| 94.140.14.14 (AdGuard DNS) | estável | traceroute ICMP | 3 | 2 BR | 900 s |
| 208.67.222.222 (OpenDNS) | estável | ping | 5 | 2 BR | 900 s |
| 208.67.222.222 (OpenDNS) | estável | traceroute ICMP | 3 | 2 BR | 900 s |
| 202.12.28.131 (APNIC) | caminho longo | ping | 5 | 2 BR | 900 s |
| 202.12.28.131 (APNIC) | caminho longo | traceroute ICMP | 3 | 2 BR | 900 s |

Intenção original (superseded-for-quota; **não** entra neste POST):
`8.8.8.8`, `1.1.1.1`, `202.12.27.33`. A primeira tentativa ao vivo
(2026-09-11) foi rejeitada pela cota global em `8.8.8.8`. Retry dessa
matriz só se a cota global liberar.

`is_oneoff: false`. One-off (`getData`) custa mais e **não** serve para a série
de treino.

As medições periódicas **continuam cobrando créditos** enquanto estão
Scheduled/Ongoing. Estimativa do card: ~210 créditos / 15 min → ~20 mil/dia.
A série ao vivo das 6 medições da tentativa 2 foi **parada** em 2026-09-11
(~23:03 UTC) pending S1.7 — ver registro abaixo.

## Persistência dos msm_id (sem a API key)

A chave fica só em `RIPE_ATLAS_API_KEY` (`.env` gitignorado, Secret ou SSM).
Os IDs **não** são a chave; podem ir para env/Secret e, depois do POST ao vivo,
para esta página.

- Arquivo local (gitignorado em `data/`): `--ids-file data/msm_ids.json`
- Env / Secret para o collector: `RIPE_ATLAS_MSM_IDS=id1,id2,id3,id4,id5,id6`
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

O comando consulta créditos antes e depois, faz **um** POST com as 6 definições
e imprime os `msm_id`. Para validar 1 ciclo (~15 min) no mesmo processo:

```bash
uv run --env-file .env python -m preditor_de_falhas_ml createPeriodic \
  --ids-file data/msm_ids.json \
  --wait-seconds 900
```

`--wait-seconds` só espera e chama o GET já existente
(`fetch_measurement_results`). Não cria outra medição.

Validação posterior (collector), um `msm_id` por vez:

```bash
uv run --env-file .env python -m preditor_de_falhas_ml getResults \
  --msm-id MSM_ID --start UNIX --stop UNIX
```

Copiar os 6 IDs e os saldos para a tabela abaixo. O primeiro ciclo pode ainda
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
# ou: RIPE_ATLAS_MSM_IDS=id1,id2,id3,id4,id5,id6
uv run --env-file .env python -m preditor_de_falhas_ml stopPeriodic
```

## Registro do POST ao vivo

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
do POST é a tentativa 2 (AdGuard / OpenDNS / APNIC).
