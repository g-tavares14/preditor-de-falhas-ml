# Implantação (módulo `implantacao-aws` de `SPEC-api-csharp.md`)

Três serviços em contêineres: `modelo` (Python, a Random Forest, só na rede interna), `api` (C#, a única porta publicada) e,
opcional, `aovivo` (consulta o RIPE Atlas a cada 60 s). Nada aqui cria recursos na AWS; isso exige o OK do dono.

## Antes do build

Os quatro arquivos que as imagens copiam **estão no git**, então um clone limpo monta e sobe sem rodar o pipeline:

| Arquivo | Para quê | Como refazer |
|---|---|---|
| `data/modelo/exportado/modelo_final.joblib` e `LEIA-ME.md` | o modelo e o SHA-256 que o serviço confere antes de abri-lo (um `.joblib` é um pickle) | `uv run python -m preditor_analise exportar` |
| `data/modelo/comparacao/escolha.json` | os parâmetros que o pacote do modelo tem de bater | `uv run python -m preditor_analise comparar` |
| `api/Preditor.Api/wwwroot/dados/replay.json` | o replay da página | `uv run python -m preditor_analise replay` |

Refazer qualquer um deles exige o Gold (que sai do Silver, e este do Bronze, que vem do BigQuery). Se refizer o `exportar`, o
SHA-256 muda: commite o `.joblib` e o `LEIA-ME.md` juntos.

O `.dockerignore` (na raiz) é uma lista de permissão: nada de `data/`, `.venv` ou credenciais entra no contexto além disso.

## Local

Da raiz do repositório:

```bash
docker compose -f deploy/docker-compose.yml up --build -d
```

- Mapa em <http://localhost:8080/>, `/testar`, `/historico`, `/swagger`, `/api/saude`. Troque a porta com `PORTA_PUBLICA=9000`.
- A porta 8001 (modelo) não é publicada: só a `api` a enxerga, pelo nome `modelo`.
- O banco SQLite fica no volume `preditor_banco` e sobrevive a `down` + `up`. `down -v` apaga o volume.

Com o serviço ao vivo (precisa de rede; a primeira partida baixa 108 h de baseline, uns 4 minutos):

```bash
docker compose -f deploy/docker-compose.yml --profile aovivo up -d
```

O `aovivo.json` aparece em `/dados/aovivo.json` (e a página em `/?ao-vivo`). O estado fica no volume `preditor_estado_aovivo`;
reiniciar retoma dele. Para sortear sondas de novo, apague esse volume. No contêiner não há Gold, por isso o comando usa
o `preditor_servico` não confere o motor contra o Gold (a conferência roda na sua máquina: `uv run python -m preditor_analise aovivo --conferir`).

## Na AWS (no ar desde 16/10/2026, conta 274394226829, us-east-1)

Endereço: **https://d3csgsins36z0x.cloudfront.net/** (o CloudFront entrega por HTTPS e fala HTTP com a instância).

| Recurso | Identificação | Para quê |
|---|---|---|
| EC2 `t4g.small` (ARM, Amazon Linux 2023, disco de 20 GB) | `i-0e4d39c1fdd61a114`, IP elástico `32.196.251.180` (`eipalloc-011c1d48b3e492563`) | roda o `docker-compose.prod.yml` (modelo, api e ao vivo) |
| Grupo de segurança | `sg-0332e91bcfda1c976` (`preditor-sg`) | só a porta 80, só a partir do CloudFront (lista de prefixos da AWS). Sem SSH, sem 8001 |
| CloudFront | `E3LILOS5GGIQ7W` | HTTPS, todos os métodos HTTP (a API usa POST), todas as bordas (`PriceClass_All`, inclui São Paulo). Respeita o `Cache-Control` do servidor: código, estilo, mapa e `replay.json` ficam 5 min no navegador e na borda (`vendor/`, 1 dia); a API, as páginas MVC e o `aovivo.json` nunca ficam em cache |
| ECR | `preditor-python` e `preditor-api` | as imagens ARM montadas neste Mac |
| IAM | função e perfil `preditor-ec2` | SSM (acesso administrativo sem SSH) e leitura do ECR |

Custo: a instância liga o tempo todo (cerca de US$ 12 a 15 por mês), mais centavos de ECR, IP elástico em uso e CloudFront.

**Atualizar** (depois de mudar o código): refaça as imagens, envie ao ECR e reinicie lá.

```bash
docker compose -f deploy/docker-compose.yml build
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 274394226829.dkr.ecr.us-east-1.amazonaws.com
for r in preditor-python preditor-api; do docker tag "${r}:latest" "274394226829.dkr.ecr.us-east-1.amazonaws.com/${r}:latest"; docker push "274394226829.dkr.ecr.us-east-1.amazonaws.com/${r}:latest"; done
aws ssm send-command --region us-east-1 --instance-ids i-0e4d39c1fdd61a114 --document-name AWS-RunShellScript \
  --parameters 'commands=["cd /opt/preditor && aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 274394226829.dkr.ecr.us-east-1.amazonaws.com && docker compose pull && docker compose up -d"]'
aws cloudfront create-invalidation --distribution-id E3LILOS5GGIQ7W --paths '/*'   # sem isto, a versão antiga fica até 5 min nas bordas
```

**Entrar na instância:** `aws ssm start-session --target i-0e4d39c1fdd61a114` (precisa do plugin Session Manager). Os arquivos ficam em `/opt/preditor`.

**Desligar tudo e parar de pagar** (nesta ordem; o CloudFront leva alguns minutos para desativar):

```bash
aws cloudfront get-distribution-config --id E3LILOS5GGIQ7W > /tmp/cf.json   # edite "Enabled": false e use o ETag em --if-match
aws cloudfront update-distribution --id E3LILOS5GGIQ7W --if-match <ETAG> --distribution-config file://cf-desligado.json
aws cloudfront wait distribution-deployed --id E3LILOS5GGIQ7W
aws cloudfront delete-distribution --id E3LILOS5GGIQ7W --if-match <NOVO_ETAG>
aws ec2 terminate-instances --region us-east-1 --instance-ids i-0e4d39c1fdd61a114
aws ec2 wait instance-terminated --region us-east-1 --instance-ids i-0e4d39c1fdd61a114
aws ec2 release-address --region us-east-1 --allocation-id eipalloc-011c1d48b3e492563
aws ec2 delete-security-group --region us-east-1 --group-id sg-0332e91bcfda1c976
aws ecr delete-repository --region us-east-1 --repository-name preditor-python --force
aws ecr delete-repository --region us-east-1 --repository-name preditor-api --force
aws iam remove-role-from-instance-profile --instance-profile-name preditor-ec2 --role-name preditor-ec2
aws iam delete-instance-profile --instance-profile-name preditor-ec2
aws iam detach-role-policy --role-name preditor-ec2 --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam detach-role-policy --role-name preditor-ec2 --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
aws iam delete-role --role-name preditor-ec2
```

Só desligar a instância (`stop-instances`) não basta: o IP elástico solto e o disco continuam cobrando.
