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

## Módulo 2: `api` (C#)

- [x] ✅ **M2.1 Esqueleto, cliente do modelo e validação** (`api/Preditor.Api/`: `Program.cs`, `Modelos/`, `Servicos/`, `Configuracao/`)
  - Aceite: `POST /api/previsoes` valida (400 com `ProblemDetails` por coluna), chama o `servico-modelo`; serviço fora do ar = 503.
- [x] ✅ **M2.2 EF Core + SQLite + histórico** (`Dados/`, migração `Inicial`)
  - Aceite: grava só o que o modelo respondeu; `GET /api/previsoes` pagina da mais nova para a mais antiga.
- [x] ✅ **M2.3 Testes e paridade** (`api/Preditor.Api.Tests/`)
  - Aceite: `dotnet test api/Preditor.sln` verde: validação, banco, 400/413/429/503, e a paridade com o Python real (310 linhas,
    100 com NaN, 1e-9). A paridade achou um erro real: o `PostAsJsonAsync` envia sem `Content-Length` e o serviço respondia 411.
- [x] ✅ **M2.4 MVC, Swagger e o site `web/`** (`Controllers/PaginasController.cs`, `Views/`, `wwwroot/api.css`)
  - Aceite: `/testar` (formulário com 3 exemplos, antiforgery), `/historico`, `/swagger`; `/` serve o mapa sem alterar `web/`.

## Módulo 3: `implantacao-aws`

Detalhado quando o módulo 2 for aprovado.
