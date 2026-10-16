# Tarefas: API em C# e microserviço do modelo

Spec: `SPEC-api-csharp.md`. Plano: `tasks/plan-api-csharp.md`.

**Regras duras:** não ler o bloco `teste`; não apagar `data/modelo/teste/TESTE_ABERTO.json`; não editar `config.py`, `modelo/`
nem `gold/`. Dependência nova (NuGet ou Python) e qualquer recurso na AWS: perguntar antes. Commits só quando o dono pedir.

## Módulo 1: `servico-modelo`

- [x] ✅ **M1.1 Previsor** (`servico_modelo/previsor.py`, `parametros.py`, `__init__.py`)
  - Aceite: `Previsor.prever` devolve classe e probabilidades na ordem do pedido; `null`/ausente = NaN; coluna desconhecida,
    não numérico (inclui booleano) e mais de 1.000 linhas são recusados com mensagem clara.
  - Verificação: `--conferir` (M1.3).
- [x] ✅ **M1.2 Servidor** (`servico_modelo/servidor.py`, `__main__.py`)
  - Aceite: `POST /prever` e `GET /saude`; 400 em JSON inválido ou com `NaN`/`Infinity`; 413 acima de 1 MB; 404/405 nas
    outras rotas; `Content-Length` em toda resposta (HTTP/1.1).
  - Verificação: `--conferir` e `curl` manual.
- [x] ✅ **M1.3 Conferência** (`servico_modelo/conferencia.py`)
  - Aceite: 0 diferenças de classe e de probabilidade (1e-12) entre o serviço e o modelo recarregado, na amostra de ~300
    linhas (com NaN, três classes); grava `api/Preditor.Api.Tests/Fixtures/paridade.json`; o processo roda sem `pyspark`
    importável; nenhuma linha do teste.
  - Verificação: `uv run python -m preditor.servico_modelo --conferir` duas vezes (mesmo arquivo).

## Módulo 2: `api` (C#) e módulo 3: `implantacao-aws`

Detalhados quando o módulo 1 for aprovado.
