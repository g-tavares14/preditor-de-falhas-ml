# S1.5 — Bucket S3 raw/curated

S3 é o “banco” do projeto: JSON bruto do Atlas e CSV curated da disciplina. Criado no mesmo stack CloudFormation de [S1.4](aws_secrets_iam.md) para a bucket policy usar o ARN da role da Lambda.

**Custo (ordem de grandeza, não cotação):** o dataset Sprint 1 é milhares de linhas JSONL/CSV — volume pequeno em [S3 Standard](https://aws.amazon.com/s3/pricing/). Intelligent-Tiering **não** entra: a taxa de monitoramento por objeto pode superar o storage nesse tamanho. Versionamento está ligado para proteger os CSV curated de overwrite acidental (custo = versões retidas; aceitável neste volume). Lifecycle aborta multipart incompleto após 7 dias.

## Região e nome

- Região padrão: **`sa-east-1`** (a mesma do S1.4).
- Bucket canônico: **`preditor-falhas-ml`**.
- Nomes de bucket são **globais**. Se estiver tomado, use `BUCKET_NAME=preditor-falhas-ml-<sufixo>` no deploy, atualize este doc e o hub Notion.

## Layout canônico

```text
s3://preditor-falhas-ml/
  raw/measurements/yyyy=/mm=/dd=/{msm_id}.jsonl
  curated/features.csv
  curated/labels.csv
  curated/log_rede.csv          # superseded (S2.1) — não gravar
```

Exemplos (não são dados reais — não commitar medições no Git):

```text
s3://preditor-falhas-ml/raw/measurements/yyyy=2026/mm=09/dd=11/12345678.jsonl
s3://preditor-falhas-ml/curated/features.csv
s3://preditor-falhas-ml/curated/labels.csv
```

`yyyy=` / `mm=` / `dd=` são partições de data da **coleta** (UTC, S1.7). `{msm_id}` é o id da medição Atlas (os 8 IDs vêm do S1.8).

Contrato curated S2.1 (dois arquivos, join `(msm_id, timestamp, prb_id)`):

- `curated/features.csv` — X + chave; **sem** `status_real`
- `curated/labels.csv` — Y + chave (`status_real`)
- `curated/log_rede.csv` — X+Y no mesmo arquivo; **superseded**. Migração: [migracao_curated_xy.md](migracao_curated_xy.md)

Hub Notion *Preditor de Falhas ML* (card S2.1) é a origem da decisão. Este card reserva o path.

Prefixos `raw/measurements/` e `curated/` ganham objetos vazios `.keep` no `deploy.sh` para o layout aparecer no console. Não são linhas do dataset.

## Quem escreve

**Somente** a role IAM da Lambda (S1.4), via identity policy + bucket policy (`s3:PutObject` e `s3:GetObject` em `raw/*` e `curated/*`; `s3:ListBucket` só nesses prefixos — senão GetObject em objeto ainda inexistente vira AccessDenied).

Humanos do grupo **não** escrevem. Leitura: group `preditor-dados-leitura` — [acesso_s3_time.md](acesso_s3_time.md). Conta dona do stack pode PutObject de verificação; isso não substitui a role.

## Segurança

| Controle | Valor | Por quê |
|---|---|---|
| Block Public Access | quatro flags `true` | card: bucket não é público |
| Object ownership | `BucketOwnerEnforced` (ACLs off) | [S3 security best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html) |
| Encryption | SSE-S3 (`AES256`) | default CFN; sem KMS extra neste volume |
| Bucket policy | Deny `aws:SecureTransport=false`; Allow Get/Put na role S1.4 em `raw/*` e `curated/*`; Allow ListBucket na mesma role só nesses prefixos | alinhada à role (não “aplicar depois”) |
| Versioning | Enabled | protege overwrite dos CSV curated |

## Deploy

```bash
export AWS_REGION=sa-east-1
./infra/aws/deploy.sh
./infra/aws/verify.sh
```

### Evidência 2026-09-11 (`sa-east-1`, conta `274394226829`)

Bucket `preditor-falhas-ml` criado; nome canônico estava livre.

```text
LocationConstraint: sa-east-1
BlockPublicAccess: BlockPublicAcls/IgnorePublicAcls/BlockPublicPolicy/RestrictPublicBuckets = true
ObjectOwnership: BucketOwnerEnforced
SSE-S3 AES256; Versioning Enabled
s3 ls: PRE curated/  PRE raw/  (+ .keep placeholders)
bucket policy Sids: DenyInsecureTransport, LambdaWriteRawCurated
  Principal Allow: arn:aws:iam::274394226829:role/preditor-falhas-s1-LambdaExecutionRole-bLuoV1hL3Slq
verify.sh: PutObject de teste como caller + delete OK; role simulation Put/GetObject = allowed
```

## Fora deste card

Lambda, EventBridge, medições Atlas, treino ML. Leitura do time: [acesso_s3_time.md](acesso_s3_time.md) (S1.5b).
