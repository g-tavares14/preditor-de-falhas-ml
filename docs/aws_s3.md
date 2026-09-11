# S1.5 — Bucket S3 raw/curated

S3 é o “banco” do projeto: JSON bruto do Atlas e CSV curated da disciplina. Criado no mesmo stack CloudFormation de [S1.4](aws_secrets_iam.md) para a bucket policy usar o ARN da role da Lambda.

**Custo (ordem de grandeza, não cotação):** o dataset Sprint 1 é milhares de linhas JSONL/CSV — volume pequeno em [S3 Standard](https://aws.amazon.com/s3/pricing/). Intelligent-Tiering **não** entra: a taxa de monitoramento por objeto pode superar o storage nesse tamanho. Versionamento está ligado para proteger `curated/log_rede.csv` de overwrite acidental (custo = versões retidas; aceitável neste volume). Lifecycle aborta multipart incompleto após 7 dias.

## Região e nome

- Região padrão: **`sa-east-1`** (a mesma do S1.4).
- Bucket canônico: **`preditor-falhas-ml`**.
- Nomes de bucket são **globais**. Se estiver tomado, use `BUCKET_NAME=preditor-falhas-ml-<sufixo>` no deploy, atualize este doc e o hub Notion.

## Layout canônico

```text
s3://preditor-falhas-ml/
  raw/measurements/yyyy=/mm=/dd=/{msm_id}.jsonl
  curated/log_rede.csv
```

Exemplos (não são dados reais — não commitar medições no Git):

```text
s3://preditor-falhas-ml/raw/measurements/yyyy=2026/mm=09/dd=11/12345678.jsonl
s3://preditor-falhas-ml/curated/log_rede.csv
```

`yyyy=` / `mm=` / `dd=` são partições de data da **coleta** (UTC, S1.7). `{msm_id}` é o id da medição Atlas (os 6 IDs vêm do S1.6).

Contrato curated (disciplina): ver hub Notion *Preditor de Falhas ML*. Este card só reserva o path.

Prefixos `raw/measurements/` e `curated/` ganham objetos vazios `.keep` no `deploy.sh` para o layout aparecer no console. Não são linhas do dataset.

## Quem escreve

**Somente** a role IAM da Lambda (S1.4), via identity policy + bucket policy (`s3:PutObject` e `s3:GetObject` em `raw/*` e `curated/*`).

Humanos do grupo **não** escrevem (S1.5b = leitura). Conta dona do stack pode PutObject de verificação; isso não substitui a role.

## Segurança

| Controle | Valor | Por quê |
|---|---|---|
| Block Public Access | quatro flags `true` | card: bucket não é público |
| Object ownership | `BucketOwnerEnforced` (ACLs off) | [S3 security best practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html) |
| Encryption | SSE-S3 (`AES256`) | default CFN; sem KMS extra neste volume |
| Bucket policy | Deny `aws:SecureTransport=false`; Allow Get/Put só na role S1.4 em `raw/*` e `curated/*` | alinhada à role (não “aplicar depois”) |
| Versioning | Enabled | protege overwrite do CSV curated |

## Deploy

```bash
export AWS_REGION=sa-east-1
./infra/aws/deploy.sh
./infra/aws/verify.sh
```

Evidência esperada (preencher o output real no PR após o primeiro deploy autenticado):

```bash
aws s3api get-public-access-block --bucket preditor-falhas-ml --region sa-east-1
aws s3api get-bucket-location --bucket preditor-falhas-ml
aws s3 ls s3://preditor-falhas-ml/raw/measurements/
aws s3 ls s3://preditor-falhas-ml/curated/
```

`get-public-access-block` deve mostrar os quatro `true`. `verify.sh` checa isso e os placeholders.

## Fora deste card

Lambda, EventBridge, medições Atlas, treino ML, acesso read-only do time (**S1.5b**).
