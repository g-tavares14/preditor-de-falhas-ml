# AGENTS.md

Instruções permanentes. Valem para **todo** incremento (coleta, rótulo, modelo,
S3/Lambda, CLI). O notebook da professora é só **exemplo** — o caminho deste
projeto é pacote Python + RIPE Atlas + AWS, não entregar a sprint no molde
desse notebook.

Storyline Scrum e contrato de dados: Notion *Preditor de Falhas ML*.
Fluxo de branch/PR: `CONTRIBUTING.md` (raiz ou `docs/`).

## Arquitetura de dados (preditor)

```text
POST (uma vez / ao reconfigurar)     GET (sempre: local + Lambda)
  cria 6 medições periódicas    →     lê /results/ dos msm_id
  destinos do projeto                  acumula raw → curated
                                      = dataset de treino
```

- **POST** — define a *fonte* do dataset: apontar aos destinos
  `8.8.8.8`, `1.1.1.1`, `202.12.27.33` (ping + traceroute ICMP, probes BR,
  `interval` 900s, `is_oneoff: false`). One-off custa mais e **não** serve
  para série de treino. Isso é setup (Sprint card S1.6), não o collector.
- **GET** — enche o dataset: `fetch` por `msm_id` + janela `start`/`stop`.
  Mesma função no driver local e na Lambda a cada 15 min (S1.2 / S1.7).
- **Lambda / collector agendado: só GET.** Nunca POST no schedule.
- Treino (sprints seguintes) consome o curated acumulado, não o payload do POST.

### Persistência

- Local (smoke): `data/raw/measurements.jsonl` — append-only.
- S3 (banco do projeto): bucket `preditor-falhas-ml`
  - raw: `raw/measurements/yyyy=/mm=/dd=/{msm_id}.jsonl`
  - curated: `curated/log_rede.csv`

### Contrato curated (canônico — disciplina)

Mínimo:

`timestamp, ip, latencia_ms, perda_pacotes_pct, jitter_ms, status_real`

Ampliado (Sprint 1):

`timestamp, prb_id, ip, latencia_ms, rtt_min_ms, rtt_max_ms, perda_pacotes_pct,`
`jitter_ms, ttl, dup, n_hops, destino_respondeu, pct_hops_timeout, status_real`

Rótulo `status_real`:

1. `perda_pacotes_pct` > 15 → `FALHA`
2. senão `latencia_ms` > 100 → `RISCO`
3. senão → `OK`

Aliases internos em inglês (`latency_ms`, `loss_pct`, `jitter_rtt_ms`) podem
existir no código; o CSV curated / contrato da disciplina usa os nomes em
português acima. Não inventar um terceiro schema.

Pergunta única do modelo: com base neste histórico, neste período, a rede está
OK, em RISCO, ou FALHA? Extras (TTL, hops, destino longo vs estável) são
diagnóstico para defesa/dashboard — não novas classes.

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
  atlas.py   _request, créditos, criar medição (POST), fetch results (GET),
             append raw local
  cli.py     argparse / env / stdout — um comando por superfície
tests/       um módulo por superfície exercitada
docs/
notebooks/   01 GET (doc S1.2), 02 POST periódico (doc S1.6) — não o collector
```

Estado atual do código: `get_credits`; `create_periodic_measurements` (POST
periódico das 6 do hub; S1.6; `is_oneoff: false`, `interval` 900);
`write_measurement_ids` (JSON dos msm_id, sem a key); `get_data` (POST one-off
+ poll — demo, não é a série de treino); `fetch_measurement_results` (GET puro
por `msm_id` + `start`/`stop`, sem poll); `append_data` (JSONL). O collector
(`getResults` / Lambda S1.7) chama só o GET — nunca `create_periodic_measurements`
nem `get_data`. O nome `get_data` **mistura** criação (POST) com leitura — não
espelhar esse padrão em código novo.

Próximos incrementos (adicionar, não confundir):

- **Função pura** de features + `status_real` (sem HTTP/Path), depois quem
  aplica no curated.

Não introduzir `domain/`, `application/`, `adapters/`, `Protocol` nem fake
“para o futuro” sem Ask.

- HTTP é `requests.request` via `_request` em `atlas.py` (Auth num só lugar).
  Sem classe de erro, sem `AtlasData`, sem pasta `services/`.
- CLI só traduz argv/stdout; não monta payload Atlas na mão.
- Fachada pública (`__init__.py`): expor só o que o README documentar; preferir
  nomes que separem create vs fetch.
- `Protocol` só com **duas** implementações reais (ex.: Atlas e PingER).
  Fonte principal do projeto: **RIPE Atlas**. PingER é referência/complemento.
- Pasta de fórmula pura só quando existir X/rótulo. Sem `requests`, argparse,
  Path, CSV, pandas nessa pasta.
- Pasta nova só com ≥2 módulos do mesmo motivo.

Capacidade nova:

1. Se for só outro request ou outro arquivo: função no módulo de I/O + comando
   na CLI + teste com HTTP/arquivo simulado.
2. Se for regra (X, falha): função pura primeiro, depois quem a aplica, depois
   o driver. Teste da regra sem I/O.
3. Collector agendado: reutilizar o GET; não reimplementar HTTP na Lambda.

Não criar `services/`, `infrastructure/` extra, nem camada que só delega.

## Dados

- HTTP: `requests`. Não trocar por `httpx` sem Ask.
- Tabela: `pandas`. Não trocar por Polars sem Ask.
- Ler Excel: `pd.read_excel(path, engine="calamine")` e dep `python-calamine`.
- Escrever Excel: `openpyxl` ou `xlsxwriter`. Calamine não grava.
- Proibido ler planilha com `openpyxl`/`xlrd` se Calamine cobre o formato.

Raw local: `data/raw/measurements.jsonl`, append-only. `append_data` acrescenta
uma linha JSON por linha do DataFrame, sem tratar RTT/perda/jitter.

Fetch (GET) devolve bruto/`DataFrame` sem rótulo. Rótulo e colunas curated só
depois da função pura e de quem a aplica (ver contrato acima).

## Always / Ask / Never

### Always

- Nomear usuário, problema e o fluxo antes de criar arquivo novo.
- Separar mentalmente POST (criar medição) de GET (ler results).
- Validar entrada na borda. Erro: o que falhou, qual valor, o que fazer.
- Type hints em API pública. `pathlib` para caminho. f-string.
- Teste de request com HTTP simulado; teste de arquivo em `tmp_path`.
- Ao terminar: o que funciona, comandos rodados, o que o fluxo ainda não faz.

### Ask before

- Contrato de CLI, formato persistido, nome público do pacote, banco/S3.
- Mudar nomes de coluna do contrato curated.
- Type checker extra (além do Pyrefly), linter além do Ruff.
- Qualquer dependência nova.
- Pasta `domain/` / `application/` / `adapters/` ou Protocol.
- Protocol sem segunda implementação real.
- Trocar destinos/cadência das 6 medições do hub.

### Never

- `pip`, secrets no git, `Exception` genérica na borda do fluxo.
- Regra de negócio no HTTP; HTTP/CSV numa fórmula pura.
- POST no collector agendado (Lambda/EventBridge).
- Interface com uma implementação.
- Camada que só delega. `*Manager` / `*Helper` / `*Utils` / `Base*` sem motivo.
- Scaffold de web/API/banco “para o futuro”.
- DI container.
- Repetir no markdown regra que o Ruff já aplica.
- Sobrescrever `data/raw/measurements.jsonl`.
- Tratar o notebook da professora como desenho obrigatório do repositório.
