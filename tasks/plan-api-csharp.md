# Plano: API em C# e microserviço do modelo

Spec: `SPEC-api-csharp.md` (aprovada em 16/10/2026). Tarefas: `tasks/todo-api-csharp.md`.

## Ordem

`servico-modelo` (Python) → `api` (C#) → `implantacao-aws`. Cada módulo termina com sua verificação antes do seguinte.

## Módulo 1: `servico-modelo`

Fatias verticais, todas em `src/preditor/servico_modelo/` (biblioteca padrão; nenhuma dependência nova):

1. `previsor.py`: valida a estrutura do pedido, monta o X de 10 colunas (`null` → NaN) e devolve classe e probabilidades.
   Só importa `ModeloExportado` e `DadosModelo` (pandas/scikit-learn, sem Spark).
2. `servidor.py` + `__main__.py`: `POST /prever`, `GET /saude`, limites de corpo e de linhas, HTTP/1.1.
3. `conferencia.py`: `--conferir` sobe o servidor numa porta livre, manda a amostra (treino + validação, com NaN, três
   classes), exige 0 diferenças contra `modelo.predict`/`predict_proba` e grava `paridade.json` para o teste do C#.

Risco: a versão do scikit-learn do pickle. Mitigação: a imagem (módulo 3) fixa a versão do `uv.lock`; `/saude` a informa.

## Módulo 2: `api` (C#)

1. Solução e `GET /api/saude`, cliente HTTP tipado do `servico-modelo`, `POST /api/previsoes` com validação (sem banco).
2. EF Core + SQLite: grava a previsão, `GET /api/previsoes`, migração.
3. Teste de paridade com o serviço real (`paridade.json`) e testes de validação.
4. MVC: `/testar` e `/historico`; servir `web/` (e `dados/`) na raiz; Swagger.

## Módulo 3: `implantacao-aws`

Dockerfiles e Compose primeiro, testados localmente; só depois a EC2, **com o OK do dono antes de criar qualquer recurso**.

## Checkpoints

Fim do módulo 1: `--conferir` com 0 diferenças e o serviço sobe sem `pyspark`. Fim do módulo 2: `dotnet test` verde
(inclui paridade) e o site abre pela API. Fim do módulo 3: `docker compose up` local serve tudo; porta do modelo fechada.
