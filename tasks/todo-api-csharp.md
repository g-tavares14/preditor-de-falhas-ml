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

## Módulo 3: `implantacao-aws` (só local; nada na AWS)

- [x] ✅ **M3.0 Entradas sem Spark e a rota do ao vivo:** `src/preditor/aovivo/__main__.py` (`python -m preditor.aovivo --sem-conferir`) e
  `GET /dados/aovivo.json` na API (`Web:ArquivoAoVivo`), com teste (41 testes passam).
- [x] ✅ **M3.1 Imagens** (`deploy/Dockerfile.python`, `deploy/Dockerfile.api`, `.dockerignore`): `docker compose -f deploy/docker-compose.yml build`
  termina (16/10/2026). `preditor-python` ~2,8 GB; `preditor-api` ~430 MB.
- [x] ✅ **M3.2 Compose no ar, local** (`deploy/docker-compose.yml`): testado em 16/10/2026. `modelo` healthy; `/api/saude`, `/swagger`, `/testar`, `/historico`, o mapa
  e `/dados/replay.json` respondem em `localhost:8080`; a 8001 não responde de fora; um POST em `/api/previsoes` devolveu a classe e as
  probabilidades da fixture de paridade; o histórico sobreviveu a `down` + `up`; com `--profile aovivo`, o `/dados/aovivo.json` aparece (200) e o estado é retomado
  depois de `restart`. Achado: o sorteio das sondas lia o Gold; `aovivo/selecao.py` agora cai no `sondas.csv` (o `replay` confere que é o mesmo conjunto).
- [x] ✅ **M3.3 `deploy/LEIA-ME.md`:** passos para montar as imagens aqui e subir na EC2 (a criação dos recursos na AWS continua exigindo o OK do dono).
