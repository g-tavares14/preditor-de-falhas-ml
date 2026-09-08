# AGENTS.md

Instruções permanentes. Valem para **todo** incremento (coleta, rótulo, modelo,
PingER, S3, CLI). Detalhe de como encaixar tipo/port/pasta nova:
`docs/organizacao.md`.

## Stack

- Python só via `uv`. Proibido: `pip`, `venv` manual, Poetry, `requirements.txt`.
- Lint/format: Ruff via `uv run`. Config só em `pyproject.toml`.
- Dep runtime: `uv add <pacote>`. Dev: `uv add --dev <pacote>`.
  Rodar: `uv run …`. Sync: `uv sync`.
- Antes de dependência nova: stdlib ou pacote já listado. Se entrar pacote,
  justificar no incremento.

## Comandos (pronto = todos verdes)

```bash
uv sync
uv run ruff format .
uv run ruff check .
uv run pytest
```

`ruff format` sem diff. `ruff check` exit 0. `--fix` só com diff revisado.

Ponto de entrada: o que o README documentar. Se o comando não rodou nesta máquina,
não escrever no README.

## Clean Architecture (todo fluxo)

```text
src/preditor_de_falhas_ml/
  domain/        entidades e regra pura
  application/   use cases e ports
  adapters/      HTTP, arquivos, CLI, futuros drivers
tests/           um módulo por camada exercitada
docs/
```

Dependency Rule: código só depende para dentro.

- `domain/`: tipos e fórmulas. Sem `requests`, argparse, Path, CSV, pandas.
- `application/`: orquestra ports. Sem frameworks. Testável com fakes.
- `adapters/`: I/O. Implementa ports. CLI só traduz argv/stdout.

Port (`Protocol`) nasce com **duas** implementações: produção + fake em
`tests/fakes.py` (ou equivalente). Use case novo recebe o port, não o
`AtlasGateway` concreto.

Fachada pública (`__init__.py`): use cases e tipos de domínio. Adapter HTTP,
arquivo ou ML **não** é a API do pacote.

Capacidade nova (rótulo, classificador, PingER, S3, API extra):

1. entidade/regra em `domain/`
2. use case + port em `application/`
3. driver em `adapters/`
4. teste do use case **sem** I/O real

Não criar `services/`, `infrastructure/` extra, nem arquivo solto na raiz do
pacote para “ir mais rápido”. Pasta nova só com ≥2 módulos do mesmo motivo.

## Dados

- HTTP: `requests`. Não trocar por `httpx` sem Ask.
- Tabela: `pandas`. Não trocar por Polars sem Ask.
- Ler Excel: `pd.read_excel(path, engine="calamine")` e dep `python-calamine`.
- Escrever Excel: `openpyxl` ou `xlsxwriter`. Calamine não grava.
- Proibido ler planilha com `openpyxl`/`xlrd` se Calamine cobre o formato.

I/O nos adapters. Transformação recebe tipo de domínio, não dict de transporte.

Coluna que entra em regra: dtype explícito. Sem inferência silenciosa em ID,
documento, código, data.

X do preditor: `latency_ms`, `loss_pct`, `jitter_rtt_ms`. Extra é diagnóstico.
Rótulo de falha só depois de regra em `domain/` e use case que a aplica.

## Always / Ask / Never

### Always

- Nomear usuário, problema e o fluxo antes de criar arquivo novo.
- Validar entrada na borda. Erro: o que falhou, qual valor, o que fazer.
- Type hints em API pública. `pathlib` para caminho. f-string.
- Teste de use case com fake; teste de adapter com I/O simulado.
- Ao terminar: o que funciona, comandos rodados, o que o fluxo ainda não faz.

### Ask before

- Contrato de CLI, formato persistido, nome público do pacote, banco.
- Type checker extra, linter além do Ruff.
- Qualquer dependência nova.
- Quarta camada, pasta fora de `domain/` `application/` `adapters/` `tests/`.
- Protocol sem fake de teste.

### Never

- `pip`, secrets no git, `Exception` genérica na borda do fluxo.
- Regra de negócio no adapter ou HTTP/CSV no `domain/`.
- Interface com uma implementação.
- Camada que só delega. `*Manager` / `*Helper` / `*Utils` / `Base*` sem motivo.
- Scaffold de web/API/banco “para o futuro”.
- DI container.
- Repetir no markdown regra que o Ruff já aplica.
