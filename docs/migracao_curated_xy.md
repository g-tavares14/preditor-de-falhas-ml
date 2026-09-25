# Migração S2.1 — `log_rede.csv` → `features.csv` + `labels.csv`

`curated/log_rede.csv` está **superseded**. O collector não grava mais nesse
objeto. Features (X) e rótulos (Y) passam a viver em arquivos separados,
com join 1:1 por `(msm_id, timestamp, prb_id)`.

Limiares de `status_real` **não mudam**: perda > 15 → `FALHA`; senão
latência > 100 → `RISCO`; senão `OK`.

Não retomar Atlas nem ligar EventBridge neste passo.

## Quando rodar

Uma vez, com EventBridge **DISABLED** (coleta Sprint 1 parada). No-op se
`curated/log_rede.csv` não existir no bucket. Idempotente se
`features.csv` / `labels.csv` já tiverem as mesmas chaves.

O collector também chama essa migração no início de cada
`collect_measurements`. Não é necessário invocar a Lambda só para migrar.

## Comando

```bash
export AWS_REGION=sa-east-1
uv run python -m preditor_de_falhas_ml migrateCurated --bucket preditor-falhas-ml
```

Sem `--bucket`, usa `S3_BUCKET` ou o nome canônico `preditor-falhas-ml`.
Não pede `RIPE_ATLAS_API_KEY`.

Saída (exemplo de forma, **não** são contagens reais do bucket):

```text
migrateCurated bucket=preditor-falhas-ml source_found=False source_rows=0 features_appended=0 labels_appended=0
curated/log_rede.csv ausente — no-op. features.csv e labels.csv não foram alterados.
```

Se o legado existir, `source_found=True` e `features_appended` /
`labels_appended` mostram quantas chaves novas foram gravadas. Conferir
contagens no S3 depois de rodar — este runbook **não** inventa números.

## O que faz

1. Lê `curated/log_rede.csv` se o objeto existir.
2. Para cada linha: X em `curated/features.csv` (sem `status_real`); Y em
   `curated/labels.csv` (`msm_id, timestamp, prb_id, status_real`).
3. Não duplica chave já presente nos arquivos novos.
4. Não apaga `log_rede.csv` (versionamento S3; objeto legado).

## Conferir (sem secret)

```bash
aws s3 ls s3://preditor-falhas-ml/curated/ --region sa-east-1
aws s3 cp s3://preditor-falhas-ml/curated/features.csv - --region sa-east-1 | head
aws s3 cp s3://preditor-falhas-ml/curated/labels.csv - --region sa-east-1 | head
```

Header esperado em features: `msm_id,timestamp,prb_id,ip,...` — sem
`status_real`. Header esperado em labels:
`msm_id,timestamp,prb_id,status_real`.
