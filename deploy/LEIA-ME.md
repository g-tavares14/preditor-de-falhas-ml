# Implantação (módulo `implantacao-aws` de `SPEC-api-csharp.md`)

Três serviços em contêineres: `modelo` (Python, a Random Forest, só na rede interna), `api` (C#, a única porta publicada) e,
opcional, `aovivo` (consulta o RIPE Atlas a cada 60 s). Nada aqui cria recursos na AWS; isso exige o OK do dono.

## Antes do build (arquivos que ficam fora do git)

As imagens copiam arquivos gerados pelo pipeline. Sem eles o build falha ou a página fica vazia:

| Arquivo | Vem de |
|---|---|
| `data/modelo/exportado/modelo_final.joblib` e `LEIA-ME.md` | `uv run python -m preditor exportar` |
| `data/modelo/comparacao/escolha.json` | `uv run python -m preditor comparar` |
| `api/Preditor.Api/wwwroot/dados/replay.json` | `uv run python -m preditor replay` |

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
`--sem-conferir` (a conferência do motor contra o Gold roda na sua máquina: `uv run python -m preditor aovivo --conferir`).

## Na EC2 (a fazer, com o OK do dono)

1. Imagens para a arquitetura da instância. Um Mac com Apple Silicon gera `arm64`; numa EC2 `x86_64` use
   `docker buildx build --platform linux/amd64 ...` (ou escolha uma instância Graviton, `arm64`, e não mude nada).
   A `preditor-python` pesa cerca de 2,8 GB (scikit-learn, pandas, scipy); a `preditor-api`, cerca de 430 MB.
2. Levar as imagens à instância: um registro (ECR) ou `docker save | gzip` + `scp` + `docker load`.
3. Copiar só `deploy/docker-compose.yml` e rodar com `PORTA_PUBLICA=80`. As imagens já estão montadas, então use `up -d` sem `--build`
   (e troque o bloco `build:` por `image:` se não levar o código-fonte).
4. Grupo de segurança: abrir só a 80 (e a 22 para o seu IP). Nunca a 8001.
5. O `.joblib` é um pickle (abrir executa código): o serviço confere o SHA-256 contra o `LEIA-ME.md` antes de abrir.
   `/api/saude` devolve esse SHA-256; ele tem de bater com o do `data/modelo/exportado/LEIA-ME.md`.
