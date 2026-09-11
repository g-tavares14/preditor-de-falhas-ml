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

O collector agendado **não** chama `createPeriodic` nem `getData`.

Documentação da disciplina (não é o collector):
`notebooks/02_post_medicoes_periodicas.ipynb`.

## Matriz do hub (fixa)

| Destino | Papel | Tipo | Pacotes | Probes | Intervalo |
|---|---|---|---|---|---|
| 8.8.8.8 | estável | ping | 5 | 2 BR | 900 s |
| 8.8.8.8 | estável | traceroute ICMP | 3 | 2 BR | 900 s |
| 1.1.1.1 | estável | ping | 5 | 2 BR | 900 s |
| 1.1.1.1 | estável | traceroute ICMP | 3 | 2 BR | 900 s |
| 202.12.27.33 | caminho longo | ping | 5 | 2 BR | 900 s |
| 202.12.27.33 | caminho longo | traceroute ICMP | 3 | 2 BR | 900 s |

`is_oneoff: false`. One-off (`getData`) custa mais e **não** serve para a série
de treino.

As medições periódicas **continuam cobrando créditos** até serem paradas no
Atlas. Estimativa do card: ~210 créditos / 15 min → ~20 mil/dia.

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

## Registro do POST ao vivo

**Estado:** bloqueado neste incremento — `RIPE_ATLAS_API_KEY` ausente no
ambiente do agente. Nenhum `msm_id` foi inventado.

| msm_id | Destino | Tipo | Papel | prb_id (1º ciclo) | timestamps | créditos antes | créditos depois |
|---|---|---|---|---|---|---|---|
| *pendente* | 8.8.8.8 | ping | estável | | | | |
| *pendente* | 8.8.8.8 | traceroute ICMP | estável | | | | |
| *pendente* | 1.1.1.1 | ping | estável | | | | |
| *pendente* | 1.1.1.1 | traceroute ICMP | estável | | | | |
| *pendente* | 202.12.27.33 | ping | caminho longo | | | | |
| *pendente* | 202.12.27.33 | traceroute ICMP | caminho longo | | | | |

Quando a chave estiver disponível: rodar o runbook, preencher a tabela, gravar
`RIPE_ATLAS_MSM_IDS` no Secret/SSM e **não** commitar a chave.
