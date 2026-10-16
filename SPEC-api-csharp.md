# SPEC: o modelo exposto por uma API em C# (e no ar na AWS)

Spec curta, no formato do projeto. Pedido do dono em 16/10/2026: para a apresentação à professora, expor o modelo por uma
API e subir o site na AWS. A API será em C# (ASP.NET Core MVC + Web API + Entity Framework Core); o Python fica só com a IA.
Esta spec **não está aprovada**: ela é para o dono revisar antes de qualquer código.

## Decisões já tomadas (16/10/2026, dono)

1. **ONNX descartado.** Convertida com o skl2onnx (float32), a floresta prevê diferente do `.joblib` em linhas com valor
   ausente (NaN): 34 de 34.661 no treino e 2 de 13.490 na validação, diferença de até 0,137 na probabilidade. A conversão
   em precisão dupla não terminou. O placar deixaria de bater com o F1 de 0,6977.
2. **Microserviço em Python só para o modelo.** A Random Forest segue sendo o `modelo_final.joblib` já validado; o C# não
   reimplementa nada do modelo, do baseline nem do rótulo.
3. **C# = MVC + Web API + EF Core**, não Blazor. A página do mapa (JavaScript) continua como está e é servida pela API.
4. **Modo ao vivo continua em Python** (o motor pandas já existe e é conferido contra o Gold). Não é portado.

## Mapa de capacidades

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `servico-modelo` | Python: abre o `.joblib` e responde `POST /prever`. Só na rede interna | — |
| `api` | C#: Web API pública, páginas MVC, banco (EF Core), serve a página `web/` | `servico-modelo` |
| `implantacao-aws` | Dockerfiles, Docker Compose e a instância EC2 | `api` |

Ordem: `servico-modelo` → `api` → `implantacao-aws`. Cada módulo se verifica antes do próximo começar.

## Premissas (corrija agora ou sigo com elas)

1. .NET 10 (SDK 10.0.401 já instalado), SQLite em arquivo (sem RDS), Docker Desktop disponível nesta máquina.
2. A API de previsão é **pública e sem login** na apresentação (só lê e prevê); proteção por limite de pedidos e de tamanho.
3. Os arquivos do modelo, o `replay.json` e o `aovivo.json` estão fora do git: as imagens são montadas **nesta máquina**.
4. O `config.py` e o código de medição do teste **não mudam** (o carimbo do teste guarda o hash deles).

## `servico-modelo` (Python)

- **Onde:** `src/preditor/servico_modelo/`. Biblioteca padrão (`ThreadingHTTPServer`), como o `servir`; **nenhuma dependência
  nova**. Reutiliza `ModeloExportado.ler()` (SHA-256 conferido antes de abrir o pickle). Sem Spark, sem Java.
- **`POST /prever`:** `{"medicoes": [ {10 colunas}, ... ]}`, no máximo 1.000 por pedido e 1 MB. Coluna ausente ou `null` =
  valor ausente (o modelo o aceita; nada é imputado, RFC §8.3). Devolve, na mesma ordem,
  `{"classe": "OK|RISCO|FALHA", "probabilidades": {"FALHA":…, "OK":…, "RISCO":…}}` e o bloco `modelo` (família, SHA-256).
- **`GET /saude`:** modelo carregado, SHA-256, colunas, versões do Python e do scikit-learn.
- **Rede:** escuta em `0.0.0.0` só dentro do contêiner; no Compose a porta **não é publicada**.
- **Comando:** `uv run python -m preditor.servico_modelo --porta 8001`; `--conferir` roda o modelo nas linhas de treino e de
  validação do Gold e grava `api/Preditor.Api.Tests/Fixtures/paridade.json` (entrada → saída esperada, ~300 linhas, incluindo
  as com NaN e as três classes). Nunca lê o bloco de teste.
- **Cuidado:** um pickle só abre com o mesmo scikit-learn de quem o gravou. A imagem fixa a versão do `uv.lock`.

## `api` (C#)

- **Onde:** `api/` (solução `Preditor.sln`): `Preditor.Api` (MVC + Web API + EF Core) e `Preditor.Api.Tests` (xUnit).
- **Web API (`/api`):** `POST /api/previsoes` (valida, chama o `servico-modelo`, grava no banco, devolve a previsão);
  `GET /api/previsoes` (histórico, paginado); `GET /api/modelo` (ficha do modelo); `GET /api/saude` (a API e o serviço);
  `/swagger` para a professora testar no navegador.
- **Validação (400 com `ProblemDetails`):** `perda_pct` entre 0 e 100; `timeout_atual` 0 ou 1; `n5_*` inteiros de 0 a 5; as
  demais, número finito; coluna desconhecida é recusada. Serviço de modelo fora do ar = 503, nunca uma previsão inventada.
- **EF Core (SQLite, `data/` no volume):** tabela `Previsoes` (`Id`, `CriadaEmUtc`, as 10 entradas anuláveis, `Classe`, três
  probabilidades, `ModeloSha256`, `Origem`). Migrações versionadas; o banco em si é ignorado pelo git.
- **MVC:** a página `/testar` (formulário com as 10 colunas e o resultado) e a `/historico`; o site do mapa (`web/`, sem
  alterar) é servido na raiz, com `dados/` vindo do volume. `/?ao-vivo` segue lendo o `aovivo.json`.
- **Segurança:** limite de taxa e de tamanho do corpo (middleware do próprio ASP.NET), nenhuma chave no repositório, o corpo
  recebido nunca é logado inteiro, a rota do `servico-modelo` vem de configuração (não do pedido).
- **Dependências que entram (confirmo antes de instalar):** `Microsoft.EntityFrameworkCore.Sqlite`,
  `Microsoft.EntityFrameworkCore.Design`, `Swashbuckle.AspNetCore`; nos testes, `xunit` e `Microsoft.AspNetCore.Mvc.Testing`.

## `implantacao-aws`

- **Onde:** `deploy/` (Dockerfile da API, Dockerfile do Python, `docker-compose.yml`, um `LEIA-ME.md` com os passos).
- **Compose:** `api` (porta 80/443, pública), `modelo` (interno), `aovivo` (o mesmo Python, outro comando; opcional) e um
  volume para o banco e para `dados/`.
- **Máquina:** uma instância EC2 `t3.small` (ou Lightsail), sempre ligada. **Nenhum recurso é criado na AWS sem o OK do dono**;
  o conector da AWS desta sessão não está autenticado, e o perfil local (`~/.aws`) só é usado se o dono mandar.
- **Fora desta spec:** domínio e certificado (HTTPS), alta disponibilidade, CI/CD.

## Estrutura

```text
src/preditor/servico_modelo/   microserviço Python (módulo 1)
api/Preditor.sln               Preditor.Api (C#) e Preditor.Api.Tests (módulo 2)
deploy/                        Dockerfiles, docker-compose.yml, LEIA-ME.md (módulo 3)
```

## Estilo do código C#

Nomes de classes e membros em português, em PascalCase (o resto do projeto é em português); um comentário por passo que não é
óbvio, sem repetir a teoria. Exemplo do tom:

```csharp
// Valor ausente fica ausente: o modelo aceita NaN, e imputar um zero esconderia um timeout (RFC §8.3).
public record Medicao(double? ZRobusto, double? AumentoPct, /* … as 10 colunas … */ double? Media5Z);
```

## Verificação

- **Python:** `uv run python -m preditor.servico_modelo --conferir` (previsão do serviço = `modelo.predict` em todas as
  linhas da amostra, incluindo as com NaN, 0 diferenças); o serviço sobe sem `pyspark` instalado.
- **C#:** `dotnet build api/Preditor.sln` e `dotnet test api/Preditor.sln`: validação (cada regra de 400), banco (grava e
  lista), e **paridade** (a API devolve a classe do `paridade.json` em todas as linhas, com o serviço real).
- **Contêineres:** `docker compose -f deploy/docker-compose.yml up --build`, e então `/api/saude`, `/swagger`, `/testar` e o
  mapa respondem; a porta do `servico-modelo` não responde de fora do Compose.
- **Placar:** o replay da página continua fechando com o F1 macro 0,6977 (N = 13.490), sem tocar no `replay.json`.

## Limites

- **Sempre:** rodar os testes antes de commitar; conferir o SHA-256 antes de abrir o `.joblib`; validar toda entrada.
- **Perguntar antes:** dependência nova (Python ou NuGet), qualquer recurso na AWS, mudar `pyproject.toml`/`uv.lock`.
- **Nunca:** editar `config.py`, `modelo/` ou `gold/`; apagar `TESTE_ABERTO.json`; ler o bloco de teste; versionar chave,
  banco ou os dados das camadas; expor a porta do `servico-modelo`.

## Perguntas em aberto

1. O modo ao vivo entra na implantação (terceiro contêiner)? Padrão proposto: sim, desligável.
2. HTTPS: há um domínio? Sem ele, a apresentação roda em HTTP, ou por um CloudFront na frente (endereço `*.cloudfront.net`).
3. Qual é a data da apresentação? Ela define se a etapa 3 (AWS) precisa ficar pronta antes de qualquer acabamento.
