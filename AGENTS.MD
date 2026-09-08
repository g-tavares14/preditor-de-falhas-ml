# AGENTS.md

Instruções permanentes do repo. Detalhe de organização está em
`docs/organizacao.md` — ler só quando a tarefa cria pasta, tipo ou camada nova.

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
uv run pytest          # só se tests/ existir
```

`ruff format` sem diff. `ruff check` exit 0. `--fix` só com diff revisado.

Ponto de entrada: o que o README documentar. Se o comando não rodou nesta máquina,
não escrever no README.

## Layout

```text
src/<pacote>/    produção
tests/           testes
docs/            detalhe que não cabe neste arquivo
pyproject.toml
uv.lock
README.md
AGENTS.md
```

Fluxo 1: no máximo entrada (CLI/função pública) + regra. Sem `services/`, `domain/`,
`infrastructure/`, `repositories/` até existir segundo uso concreto.

## Dados

Quando o fluxo precisar — não `uv add` no repo vazio:

- HTTP: `requests`. Não trocar por `httpx` sem Ask.
- Tabela: `pandas`. Não trocar por Polars sem Ask.
- Ler Excel: `pd.read_excel(path, engine="calamine")` e dep `python-calamine`.
- Escrever Excel / formatação: `openpyxl` ou `xlsxwriter`. Calamine não grava.
- Proibido ler planilha com `openpyxl` ou `xlrd` se Calamine cobre o formato
  (`xlsx`, `xlsm`, `xlsb`, `xls`, `ods`).

I/O (HTTP, arquivo) fora da transformação. Transformação recebe DataFrame ou path
já resolvido.

Coluna que entra em regra: dtype explícito. Sem inferência silenciosa em ID,
documento, código, data.

## Always / Ask / Never

### Always

- Nomear usuário, problema e o fluxo antes de criar arquivo novo.
- Validar entrada na borda. Erro: o que falhou, qual valor, o que fazer.
- Type hints em API pública. `pathlib` para caminho. f-string.
- Separar regra de I/O quando I/O existir de fato.
- Ao terminar: o que funciona, comandos rodados, o que o fluxo ainda não faz.

### Ask before

- Decisão difícil de reverter: contrato de CLI, formato persistido, nome público
  do pacote, banco, type checker extra, linter além do Ruff.
- Qualquer dependência nova.
- Hierarquia, Protocol/ABC, ou pasta nova além de `src/<pacote>/` e `tests/`.

### Never

- `pip`, secrets no git, `Exception` genérica na borda do fluxo.
- Interface/ABC com uma implementação.
- Camada que só delega. `*Manager` / `*Helper` / `*Utils` / `Base*` sem justificativa.
- Scaffold de web/API/banco “para o futuro”.
- Repetir no markdown regra que o Ruff já aplica.

## Primeiro incremento (repo vazio)

- Usuário + problema + fluxo 1 (perguntar se faltar).
- Pacote em `src/`, Ruff no `pyproject.toml`.
- Entrada real com validação.
- README com os comandos acima, executados.
- Gates verdes.
