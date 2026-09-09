# AGENTS.md

Instruções permanentes. Valem para **todo** incremento (coleta, rótulo, modelo,
PingER, S3, CLI). Detalhe de como encaixar tipo ou pasta nova:
`docs/organizacao.md`.

## Stack

- Python só via `uv`. Proibido: `pip`, `venv` manual, Poetry, `requirements.txt`.
- Lint/format/imports: Ruff via `uv run`. Config só em `pyproject.toml`.
  Proibido: Black, isort, flake8, Pylint.
- Types e language server: Pyrefly. Proibido no mesmo workspace: mypy,
  Pyright, Cursor Pyright, ty, basedpyright, Pylance.
- Testes: pytest. Não usar unittest como runner padrão.
- Editor (Cursor): `ms-python.python` para interpretador, debug e testes.
  `python.languageServer = None`. O LSP de tipos é o Pyrefly.
- Dep runtime: `uv add <pacote>`. Dev: `uv add --dev <pacote>`.
  Rodar: `uv run …`. Sync: `uv sync`.
- Antes de dependência nova: stdlib ou pacote já listado. Se entrar pacote,
  justificar no incremento.
- Tipos em funções públicas e APIs internas que cruzam módulo.
- Sem `# type: ignore` / `# pyrefly: ignore` sem comentário curto com o motivo.
  Prefira correção real a silenciar diagnóstico.

## Comandos (pronto = todos verdes)

```bash
uv sync
uv run ruff check --fix
uv run ruff format
uv run pyrefly check
uv run pytest
```

`ruff format` sem diff. `ruff check` exit 0. `--fix` só com diff revisado.
`pyrefly check` exit 0.

Ponto de entrada: o que o README documentar. Se o comando não rodou nesta máquina,
não escrever no README.

## Forma do pacote

```text
src/preditor_de_falhas_ml/
  atlas.py   _request, get_credits, get_data (DataFrame), append_data (JSONL)
  cli.py     argparse / env / stdout
tests/       um módulo por superfície exercitada
docs/
```

Hoje o fluxo é request + DataFrame + arquivo. Não introduzir `domain/`,
`application/`, `adapters/`, `Protocol` nem fake “para o futuro”.

- HTTP é `requests.request` via `_request` em `atlas.py` (Auth num só lugar).
  Sem classe de erro, sem `AtlasData`, sem pasta `services/`.
- CLI só traduz argv/stdout; não monta payload Atlas na mão.
- Fachada pública (`__init__.py`): `get_credits`, `get_data`, `append_data`.
- `Protocol` só com **duas** implementações reais (ex.: Atlas e PingER).
- `domain/` só quando existir fórmula (X, rótulo). Sem `requests`, argparse,
  Path, CSV, pandas nessa pasta.
- Pasta nova só com ≥2 módulos do mesmo motivo.

Capacidade nova:

1. Se for só outro request ou outro arquivo: função no módulo de I/O + comando
   na CLI + teste com HTTP/arquivo simulado.
2. Se for regra (X, falha): função pura primeiro, depois quem a aplica, depois
   o driver. Teste da regra sem I/O.

Não criar `services/`, `infrastructure/` extra, nem camada que só delega.

## Dados

- HTTP: `requests`. Não trocar por `httpx` sem Ask.
- Tabela: `pandas`. Não trocar por Polars sem Ask.
- Ler Excel: `pd.read_excel(path, engine="calamine")` e dep `python-calamine`.
- Escrever Excel: `openpyxl` ou `xlsxwriter`. Calamine não grava.
- Proibido ler planilha com `openpyxl`/`xlrd` se Calamine cobre o formato.

Raw de coleta: `data/raw/measurements.jsonl`, append-only. `get_data` só
devolve DataFrame (uma linha por item de `/results/`). `append_data` acrescenta
uma linha JSON por linha do DataFrame, sem tratar RTT/perda/jitter.

X do preditor, quando existir: `latency_ms`, `loss_pct`, `jitter_rtt_ms`.
Extra é diagnóstico. Rótulo de falha só depois de regra pura e de quem a aplica.

## Always / Ask / Never

### Always

- Nomear usuário, problema e o fluxo antes de criar arquivo novo.
- Validar entrada na borda. Erro: o que falhou, qual valor, o que fazer.
- Type hints em API pública. `pathlib` para caminho. f-string.
- Teste de request com HTTP simulado; teste de arquivo em `tmp_path`.
- Ao terminar: o que funciona, comandos rodados, o que o fluxo ainda não faz.

### Ask before

- Contrato de CLI, formato persistido, nome público do pacote, banco.
- Type checker extra (além do Pyrefly), linter além do Ruff.
- Qualquer dependência nova.
- Pasta `domain/` / `application/` / `adapters/` ou Protocol.
- Protocol sem segunda implementação real.

### Never

- `pip`, secrets no git, `Exception` genérica na borda do fluxo.
- Regra de negócio no HTTP; HTTP/CSV numa fórmula pura.
- Interface com uma implementação.
- Camada que só delega. `*Manager` / `*Helper` / `*Utils` / `Base*` sem motivo.
- Scaffold de web/API/banco “para o futuro”.
- DI container.
- Repetir no markdown regra que o Ruff já aplica.
- Sobrescrever `data/raw/measurements.jsonl`.
