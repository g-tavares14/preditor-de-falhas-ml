# S1.5b — Acesso read-only do time ao S3

O bucket `preditor-falhas-ml` continua **privado**. Quem escreve é só a role da Lambda ([S1.4](aws_secrets_iam.md)). O Grupo 16 lê pelo IAM group `preditor-dados-leitura` — **não** pela role da Lambda e **não** pela API key do Atlas.

IAM **groups não podem** ser `Principal` em bucket policy. A leitura é identity-based (policy gerenciada no group).

## O que já existe (conta `274394226829`, `sa-east-1`)

| Recurso | Nome |
|---|---|
| Group | `preditor-dados-leitura` |
| Policy | `preditor-dados-leitura` (`ListBucket` só em `raw`/`curated` + `GetObject` nesses prefixos) |
| Bucket | `preditor-falhas-ml` |

Sem `s3:PutObject` / `DeleteObject`. Sem `secretsmanager:*`.

## Como cada pessoa entra no group

1. O dono da conta (Guilherme) cria **um usuário IAM por integrante** (não compartilhem o root):

```bash
./infra/aws/add-team-user.sh preditor-ingrid
```

2. No console IAM → Users → esse usuário → **Create login password** (ou Access key só se a pessoa for usar CLI). Marcar *User must create a new password at next sign-in*.
3. Enviar usuário + senha temporária **por canal privado** (não WhatsApp do grupo com a key do Atlas; não Git/PR).
4. A pessoa configura `aws login` ou `AWS_PROFILE` e testa o download abaixo.

Não criem access key da **role da Lambda**. Não compartilhem `RIPE_ATLAS_API_KEY`.

Integrantes do Grupo 16 (usernames sugeridos; o dono da conta já acessa como root e **não** precisa deste group para administrar):

| Pessoa | Username IAM sugerido |
|---|---|
| Alexandre Tiago de Oliveira | `preditor-alexandre` |
| Ingrid Ferreira de Sousa | `preditor-ingrid` |
| Kauan Garcia Dias de Oliveira | `preditor-kauan` |
| Lucas Eduardo Malachias Bagatela | `preditor-lucas` |
| Stephanie Vitoria Bessa dos Santos | `preditor-stephanie` |

## Como baixar o curated

CLI (região `sa-east-1`):

```bash
aws s3 ls s3://preditor-falhas-ml/curated/ --region sa-east-1
aws s3 cp s3://preditor-falhas-ml/curated/log_rede.csv . --region sa-east-1
```

Raw (debug da coleta), opcional:

```bash
aws s3 ls s3://preditor-falhas-ml/raw/measurements/ --region sa-east-1
```

Console: S3 → bucket `preditor-falhas-ml` → `curated/log_rede.csv` → Download.  
Se o bucket não aparecer na lista da home do S3, abra o objeto direto:

`https://s3.console.aws.amazon.com/s3/object/preditor-falhas-ml?region=sa-east-1&prefix=curated/log_rede.csv`

A policy **não** inclui `s3:ListAllMyBuckets` (de propósito).

Não commitar o CSV grande no Git. Sample pequeno ok se o grupo decidir.

## Prova (sem usuário de colega)

```bash
./infra/aws/verify.sh
```

O script simula o **group**: `GetObject` allowed, `PutObject` e `GetSecretValue` implicitDeny. O teste “1 pessoa além do dono consegue baixar” só fecha depois de um integrante entrar no group e rodar o `aws s3 cp` acima.
