# S1.7 — Lambda collector + EventBridge

Collector GET-only no stack **já existente** `preditor-falhas-s1` (`sa-east-1`,
conta `274394226829`). Não cria outro stack.

```text
S1.2 fetch_measurement_results(...)  →  raw JSONL no S3
S1.3 curated_row / status_real       →  curated/log_rede.csv
Lambda = schedule + I/O S3 + orquestra os dois
```

Sem POST: o handler **não** chama `create_periodic_measurements` nem `get_data`.

## Recursos

| Recurso | Nome | Notas |
|---|---|---|
| Função | `preditor-falhas-collector` | Python 3.12, timeout 60s, 512 MB, x86_64 |
| Role | `preditor-falhas-s1-LambdaExecutionRole-bLuoV1hL3Slq` | a mesma do S1.4 — não recriar |
| Secret | `RIPE_ATLAS_API_KEY` | `GetSecretValue` no runtime; **nunca** em env |
| Bucket | `preditor-falhas-ml` | raw + curated (S1.5) |
| Regra | `preditor-falhas-collector-15min` | `rate(15 minutes)` |
| Zip | `s3://preditor-falhas-ml/artifacts/lambda/preditor-falhas-collector.zip` | build `infra/aws/package.sh` |

Handler: `preditor_de_falhas_ml.handler.lambda_handler`.

## Empacotamento (monorepo zip)

Um zip com o pacote + `pandas` + `requests`, pins do `uv.lock`.
`boto3` **fica de fora** — o runtime Python 3.12 da Lambda já traz o SDK.

Por que não layer: um artefato só, mesmo `import` do desenvolvimento local,
sem segunda árvore de deps. `infra/aws/package.sh` é reproduzível (`uv export
--frozen` + `uv pip install --target --only-binary :all:`).

## Variáveis de ambiente

| Variável | Valor |
|---|---|
| `S3_BUCKET` | `preditor-falhas-ml` |
| `RIPE_ATLAS_MSM_IDS` | `id1,id2,…` dos **novos** IDs do `createPeriodic` (não os Stopped) |
| `SECRET_NAME` | `RIPE_ATLAS_API_KEY` |
| `COLLECT_WINDOW_SECONDS` | `1200` (20 min; overlap da cadência de 15 min) |

A API key **não** entra em env. O handler lê o Secret e **não** loga o valor.

`ATLAS_MSM_IDS` no runbook S1.4 era o nome *previsto*. O nome aplicado é
`RIPE_ATLAS_MSM_IDS` (o mesmo da CLI e de `parse_measurement_ids_csv`).

## Janela e idempotência

Janela fixa: `[now − 1200, now]` (unix UTC). Invoke manual pode passar
`start` / `stop` / `msm_ids` no payload (GET histórico).

Raw: `raw/measurements/yyyy=/mm=/dd=/{msm_id}.jsonl` (data UTC do `stop`).
Curated: append `curated/log_rede.csv`. Chave de idempotência:
`msm_id + timestamp + prb_id`. `msm_id` é coluna operacional no CSV; as 14
colunas da disciplina vêm na ordem canônica. A role precisa de
`s3:ListBucket` nos prefixos `raw`/`curated`: sem isso, GetObject em
objeto ainda inexistente vira AccessDenied em vez de `NoSuchKey`.

## Kill-switch

A regra nasce **DISABLED**. Ligar só depois de: zip no S3, invoke manual OK,
e `RIPE_ATLAS_MSM_IDS` com IDs **novos** do `createPeriodic`.

```bash
# desligar (kill-switch)
aws events disable-rule \
  --name preditor-falhas-collector-15min \
  --region sa-east-1

# ou no próximo deploy
SCHEDULE_STATE=DISABLED ./infra/aws/deploy.sh

# ligar (só com IDs Ongoing)
aws events enable-rule \
  --name preditor-falhas-collector-15min \
  --region sa-east-1
```

## Deploy

```bash
export AWS_REGION=sa-east-1
# IDs novos depois do createPeriodic; vazio no primeiro deploy
export RIPE_ATLAS_MSM_IDS='id1,id2,id3,id4,id5,id6'
export SCHEDULE_STATE=DISABLED
./infra/aws/deploy.sh
./infra/aws/verify.sh
```

## Invoke manual

Prova do path S3 com histórico dos IDs **Stopped** (não voltam a emitir):

```bash
cat > /tmp/collector-stopped.json <<'JSON'
{
  "msm_ids": "210717688,210717689,210717690,210717691,210717692,210717693",
  "start": 1789166700,
  "stop": 1789167900
}
JSON
INVOKE_PAYLOAD=/tmp/collector-stopped.json ./infra/aws/invoke.sh
```

Depois do `createPeriodic` (novos IDs), atualize env e invoque sem payload
(janela de 20 min). Só então `enable-rule`.

Conferir objetos (sem secret):

```bash
aws s3 ls s3://preditor-falhas-ml/raw/measurements/ --recursive --region sa-east-1
aws s3 cp s3://preditor-falhas-ml/curated/log_rede.csv - --region sa-east-1 | head
```

## createPeriodic (novos IDs — fora da Lambda)

Os IDs `210717688`–`210717693` estão Stopped. Atlas não reinicia. A série
Ongoing é outro POST:

```bash
uv run --env-file .env python -m preditor_de_falhas_ml createPeriodic \
  --ids-file data/msm_ids.json
```

Copiar a linha `export RIPE_ATLAS_MSM_IDS=…` para o env da Lambda
(`./infra/aws/deploy.sh` ou `update-function-configuration`). Não inventar IDs.
Se o POST falhar por cota, **deixar a regra DISABLED** e registrar em
`docs/dataset-fonte-atlas.md`.

## Fora deste card

Treino da árvore, Streamlit, mudar destinos do hub, compartilhar a key
da Lambda com o time.
