# Tarefas — Go + React (`SPEC-go-react.md`)

Linha de base: `dotnet test api/Preditor.sln` = 42 testes verdes (20/10/2026). Nada de commit/push/deploy sem o dono pedir.

## Etapa 1 — Backend em Go

- [x] T1 Ler o backend C#, os testes e o acoplamento do Python com `api/Preditor.Api/` (só `config.py` e `servico_modelo/parametros.py`).
- [x] T2 `servidor/`: módulo Go, `configuracao`, `medicao` (tipo, decodificação estrita, `Validar`), `modelo` (cliente do Python), `banco` (SQLite, mesma tabela do EF), `previsao`.
- [x] T3 `api`: rotas, problem+json, corpo máximo, limite por IP, `CrossOriginProtection`, site estático com cache, `aovivo.json`.
- [x] T4 Delegada pelo dono ("pode implementar tudo"): as quatro regras de `medicao/validar.go` (`finito`, `faixa`, `binaria`, `inteiro`).
- [x] T5 Testes portados dos 42 do C# + banco no formato do EF + 415/403/origem.
- [x] T6 Paridade com o Python real (pulada sem `uv`); `ARQUIVO_PARIDADE` aponta para o `testdata/` do Go; o fixture foi copiado (o `conferir_servico` o regrava no lugar novo).
- [x] T7 `openapi.json` à mão + Swagger UI local (`/swagger`), com teste do contrato.
- [x] T8 `deploy/Dockerfile.api` (Go) e `.dockerignore`; conferir a imagem no Docker local, se houver Docker.
- [x] T9 Conferir à mão: `go run` + Python no ar + mapa abrindo pela página atual; `go vet` limpo.

## Etapa 2 — Frontend React + TypeScript

- [x] T10 `web/`: Vite + React + TS strict + Vitest + router; tipos do `replay.json`.
- [x] T11 Porte da lógica pura com testes: `tempo`, `placar`, `aovivo`, `comum`, `rotas`.
- [x] T12 Porte do mapa imperativo: `mapa`, `desenho`, `pulsos`, `selos`, `foco`; componente `<Mapa>`; laço de animação fora do React.
- [x] T13 Componentes: relógio, filtro, legenda, cartão da conexão, placar, feed, menu de modos, `?ao-vivo`.
- [x] T14 `Testar` e `Historico` (formulário, erros por coluna, 503, paginação).
- [x] T15 Go serve `web/dist` com fallback do SPA, CSP por cabeçalho e cache com hash; Python passa a gravar em `web/public/dados`.
- [x] T16 Conferir no navegador: placar ao fim do replay = JSON = comparação; pular na barra = tocar até lá; teclado; `?ao-vivo`.
- [x] T17 `Dockerfile.api` em três estágios, composes, `deploy/LEIA-ME.md`, `AGENTS.md`, `README.md`.

## Depois (fora desta spec, só com o OK do dono)

- [x] Remover `api/` (C#) e a menção ao .NET (feito em 20/10/2026; continua no histórico do git).
- [ ] Deploy na instância (editar o `docker-compose.prod.yml` de lá) e invalidar o CloudFront.
