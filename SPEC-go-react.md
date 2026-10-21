# SPEC — Backend em Go e frontend em React + TypeScript

Troca a API em C# (`api/`) por um servidor em **Go** (`servidor/`) e a página em JavaScript puro (`api/Preditor.Api/wwwroot/`) por um app
**React + TypeScript** (`web/`). O comportamento que o público vê não muda; muda a tecnologia. As tarefas estão em
`tasks/todo-go-react.md` (a ordem das etapas está abaixo; não há `plan-` à parte).

## Decisões do dono (20/10/2026)

1. **Ordem:** Go primeiro, servindo a página atual; React depois. Duas etapas, cada uma com os testes verdes antes da seguinte.
2. **`/testar` e `/historico`** viram rotas do app React, falando com `/api/previsoes`. Some o antiforgery do Razor.
3. **Swagger:** `openapi.json` escrito à mão + Swagger UI local (arquivos no repositório, sem CDN), em `/swagger`.
4. **Caminhos do Python podem mudar** (só caminhos; `config.py` segue sem mudar um único resultado).

## O que não muda

- O **microserviço do modelo** (`src/preditor_servico/servico_modelo/`, Python) e o **serviço ao vivo**. A Random Forest é um `.joblib`
  (pickle do scikit-learn): o Go só pergunta a ela por HTTP, como o C# fazia. Sem reimplementar inferência.
- O pipeline de dados, o treino e o `replay.json` (formato idêntico).
- Nada de commit, push, deploy ou recurso novo na AWS sem pedido do dono. O `docker-compose.prod.yml` que está na instância
  (`/opt/preditor`) é editado à mão pelo dono no próximo deploy (ver "Implantação").

## Etapa 1 — Backend em Go (`servidor/`)

Biblioteca padrão (`net/http` com os padrões de rota do Go 1.22+, `log/slog`, `database/sql`) mais **um** driver: `modernc.org/sqlite`
(Go puro, sem CGO, para a imagem ARM montar no Mac). Pacotes em português, sem acento: `medicao`, `modelo`, `banco`, `previsao`, `api`,
`configuracao`.

### Contrato HTTP (preservado do C#; a linha de base são os 42 testes de `api/Preditor.Api.Tests/`)

| Rota | Comportamento |
|---|---|
| `POST /api/previsoes[?origem=api\|formulario]` | `Content-Type: application/json` (senão 415). Corpo: as 10 colunas, cada uma número ou `null`/ausente. Coluna desconhecida, texto no lugar de número, `NaN`, JSON torto ou lixo depois do objeto: **400**. Fora de faixa: **400** com `errors["coluna"] = ["mensagem"]`. 200: `{id, criadaEmUtc, classe, probabilidades{FALHA,OK,RISCO}, modeloSha256}`. `origem` omitida = `api`; outro valor = 400. |
| `GET /api/previsoes?pagina=1&tamanho=20` | Da mais nova para a mais antiga (`CriadaEmUtc desc, Id desc`). `pagina` ≥ 1 e `tamanho` de 1 a 100, senão 400. `{pagina, tamanho, total, itens:[{previsao, entrada, origem}]}`. `itens` nunca é `null`. |
| `GET /api/modelo` | O `/saude` do Python, repassado cru. |
| `GET /api/saude` | **Sempre 200**: `{api:"ok", modelo:"ok"\|"fora do ar", sha256}`. O Compose usa como "a API está viva". |
| `GET /dados/aovivo.json` | Lê o arquivo de `Web__ArquivoAoVivo`; 404 se faltar; `Cache-Control: no-cache`; `application/json`. |
| arquivos do site | `vendor/` com `max-age=86400`; o resto `max-age=300`; **só em respostas 200/304** (nunca cachear um 404). Sem listagem de pasta e sem arquivo oculto (`.DS_Store`). |
| `/swagger`, `/api/openapi.json` | Swagger UI local e o contrato escrito à mão. |

Erros são `application/problem+json`. Modelo fora do ar, lento, com status ≠ 2xx, com JSON torto ou com resposta que não é "uma previsão +
`modelo.sha256`" = **503**, **nada é gravado**. Qualquer outra falha = 500 com mensagem genérica (o detalhe só vai ao log).
Corpo acima de `Limites__CorpoMaximoBytes` (16.384): **413**, tanto por `Content-Length` (antes de ler) quanto por corpo em pedaços
(`http.MaxBytesError`). Mais de `Limites__PedidosPorMinuto` (60) por IP em `/api/*`: **429** (janela fixa de 1 min; o site estático não conta).
`http.CrossOriginProtection` recusa POST de navegador vindo de outra origem (403).

### Pontos onde o Go erra se ninguém avisar

- **Ausente é `null`, não zero.** Colunas são `*float64` **sem** `omitempty`: o Python recebe as 10 chaves, as ausentes como `null` explícito
  (imputar zero esconderia um timeout; RFC §8.3). Há teste que confere o corpo enviado ao modelo.
- **Decodificação estrita:** `DisallowUnknownFields`, um só objeto no corpo, `null` sozinho recusado.
- **Corpo para o Python com `Content-Length`** (`bytes.Reader`): o serviço Python recusa corpo em pedaços (411).
- **Datas:** o banco guarda `yyyy-MM-dd HH:mm:ss.FFFFFFF` em UTC (formato do EF Core); o JSON sai em RFC 3339 com `Z`.
- **NaN passa em `>=`/`<=` ao contrário:** toda regra de faixa precisa recusar NaN de propósito.

### Variáveis de ambiente

Mantidas as duas que o `docker-compose.prod.yml` da instância já usa: `ServicoModelo__Url` e `Web__ArquivoAoVivo`. Novas, no mesmo estilo:
`Web__OrigensConfiaveis` (vazio; o endereço público atrás do CloudFront, para a proteção contra POST de outra origem não recusar o do próprio site), `ServicoModelo__TimeoutSegundos` (10), `Limites__PedidosPorMinuto` (60), `Limites__CorpoMaximoBytes` (16384), `Banco__Arquivo`
(`dados/preditor.db`), `Servidor__Endereco` (`:5053` local, `:8080` no contêiner), `Web__Pasta` (onde estão `index.html` e os assets).

### Banco

O mesmo arquivo SQLite, a mesma tabela `Previsoes` e as mesmas colunas e índice da migração `Inicial` do EF (`CREATE ... IF NOT EXISTS`).
O volume `banco` da produção (com o histórico) abre sem migrar nada. A tabela `__EFMigrationsHistory` fica no arquivo e é ignorada.

### Aceitação da etapa 1

- `go test ./...` verde, com os mesmos casos dos 42 testes em C#.
- **Paridade:** o Go falando com o Python de verdade (`uv run python -m preditor_servico.servico_modelo`) devolve, em cada linha de
  `paridade.json`, a mesma classe e as mesmas probabilidades (1e-9), com ≥ 100 linhas com NaN e as 3 classes. O teste é pulado se o `uv`
  não estiver no PATH, e diz isso.
- Com o `Web__Pasta` apontando para a página atual, o mapa abre e o replay toca como antes. (`/testar` e `/historico` só voltam na
  etapa 2: **a etapa 1 não vai sozinha para produção.**)
- Python: `ARQUIVO_PARIDADE` passa a `servidor/internal/api/testdata/paridade.json`.

## Etapa 2 — Frontend em React + TypeScript (`web/`)

Vite + React + TypeScript `strict` + `react-router` + Vitest. D3 e TopoJSON saem de `vendor/` e viram dependências npm (empacotadas pelo
Vite, sem CDN); o `countries-110m.json` fica em `web/public/`. O Go serve `web/dist` de `Web__Pasta`, com fallback para `index.html`
nas rotas do app (`/testar`, `/historico`).

### Arquitetura

- **Lógica pura primeiro, com testes:** `tempo.ts`, `placar.ts`, `aovivo.ts`, `comum.ts`, `rotas.ts` (porte fiel de `tempo.js`, `placar.js`,
  `aovivo.js`, `comum.js`, `rotas.js`), com tipos para o formato do `replay.json`. Vitest cobre o que hoje só "roda em Node" sem teste.
- **O mapa fica imperativo.** `mapa`, `desenho`, `pulsos`, `selos`, `foco` (D3, SVG e canvas a 60 fps) viram módulos TS atrás de um
  componente `<Mapa>` que os monta por `ref`. **O relógio de 60 quadros nunca entra em estado do React**: um laço de
  `requestAnimationFrame` fora do React empurra, no máximo 10 vezes por segundo, um instantâneo (placar, contadores, hora, feed) para a
  árvore React por `useSyncExternalStore`.
- **React só onde há DOM de verdade:** relógio e controles, filtro de regiões, legenda, cartão da conexão, placar, feed, e as telas
  `Testar` e `Historico`. Sem `dangerouslySetInnerHTML`; texto sempre por JSX.
- **CSP** `default-src 'self'; base-uri 'none'` passa de `<meta>` para **cabeçalho HTTP do Go** nas respostas HTML (o servidor de
  desenvolvimento do Vite injeta um script inline que o `<meta>` bloquearia). A `index.html` construída não pode ter script inline
  (conferido por teste). A página do Swagger tem a sua própria CSP, mais frouxa.
- **`/testar`:** formulário controlado com as 10 colunas, textos de ajuda e os 3 exemplos (hoje em `ColunasDoModelo.cs`) em
  `web/src/colunas.ts`; envia `POST /api/previsoes?origem=formulario` e mostra `errors[coluna]` ao lado do campo, o 503 como aviso
  ("nada foi gravado") e a previsão com barras. **`/historico`:** `GET /api/previsoes` com paginação.
- **Cache:** arquivos com hash em `assets/` ganham `max-age=31536000, immutable`; `index.html` (e `/testar`, `/historico`) ficam `no-cache`; `mapa/` 1 dia;
  `replay.json` 5 min. Muda em relação a antes (5 min para tudo) e elimina a invalidação do CloudFront a cada versão (só o `replay.json` mantém o nome).
- CSS: `estilo.css` e `api.css` migram quase sem mudança (as classes continuam as mesmas).

### Aceitação da etapa 2

- `npm run build` e `npm test` verdes; `tsc --noEmit` sem erro; `index.html` construída sem `<script>` inline.
- No navegador, ao fim do replay o **placar da página é igual ao do JSON e ao da comparação** (Random Forest: F1 macro 0,6977, N = 13.490;
  acertos da floresta e do palpite simples iguais aos de `comparacao_modelos.csv`). Pular na barra de tempo dá o mesmo estado que tocar.
- Modo `?ao-vivo` carrega com um `aovivo.json` de amostra; teclado (espaço, Esc, setas) e leitor de tela como antes.
- `/testar` e `/historico` fazem o que as páginas Razor faziam; depois do envio, a linha aparece em `/historico` com origem `formulario`.

## Implantação (a ser feita pelo dono)

- `deploy/Dockerfile.api` vira um build em três estágios (Node → Go → imagem mínima). `.dockerignore` e os dois `docker-compose` mudam o
  ponto de montagem do volume `vivo` do contêiner Python (`/app/web/public/dados`, que é onde `config.WEB` passa a apontar).
- **O `docker-compose.prod.yml` da instância precisa da mesma mudança de montagem**, e o CloudFront deve ser invalidado uma vez
  (`/*`), porque o nome dos arquivos muda.
- Remoção do C# (`api/`, `.NET` no AGENTS.md) só depois da etapa 2 passar, num passo à parte.

## Riscos

| Risco | Mitigação |
|---|---|
| O Go diverge do C# em algum canto do contrato | Casos de teste portados um a um, mais a paridade com o Python real |
| Regressão visual/temporal no mapa ao portar para React | Lógica pura portada com testes antes; mapa imperativo; conferência do placar ao fim do replay |
| O volume de produção não abre | Mesma tabela e mesmo formato de data; teste que lê uma linha escrita no formato do EF |
| Mudar `config.py` afeta o Python | Só 3 constantes de caminho; `arvore`, `ajuste`, `comparar`, `replay` seguem iguais (conferir `replay` com a mesma saída) |

## Resultado (20/10/2026)

Etapas 1 e 2 prontas e verificadas; o C# (`api/`) foi removido do working tree (continua no histórico do git). **Nada foi commitado, enviado nem publicado.**

| Critério | Resultado |
|---|---|
| `go test ./...` | verde (api, banco, configuração, medição), incluindo a paridade com a Random Forest de verdade |
| Paridade Go × Python | 310 linhas (100 com NaN), as 3 classes, iguais a 1e-9; SHA-256 do modelo igual ao da amostra |
| Volume de produção | um SQLite escrito pela API em C# abre no Go (leu 2 linhas antigas, gravou a terceira, ordem certa, dono 1654) |
| `npm run build` e `npm test` | `tsc` sem erro; 85 testes de Vitest; `index.html` sem script nem estilo inline (JS 358 kB, 116 kB com gzip) |
| Aceitação (placar ao fim do replay) | 11.535 de 13.490 (sistema) e 11.018 de 13.490 (palpite simples): as diagonais das matrizes da comparação; F1 macro 0,6977. No teste e no navegador |
| Pular na barra = tocar até lá | teste em 7 instantes; o porte do `tempo`/`placar` foi comparado ao JS antigo em 41 instantes (idênticos) |
| `replay` regerado | byte a byte igual (mesmo SHA-256) com o novo caminho |
| Imagem da API | 34 MB (era 436 MB); sobe no Compose com o modelo; `healthy`; CSP por cabeçalho; cache por tipo de arquivo |
| Navegador | replay (toca, termina, botão Reiniciar), seleção por teclado e Esc devolvendo o foco, filtro de regiões, `?ao-vivo` (relógio atrasado, selo "dados de há N s"), troca de modo sem recarregar, `/testar` (erro por campo, 503), `/historico`, layout de celular sem rolagem horizontal |

### O que ficou de fora (precisa do OK do dono)

- Commit e push. Publicar na AWS (ver "Primeira publicação do Go + React" em `deploy/LEIA-ME.md`, que inclui editar o `docker-compose.prod.yml` da instância e guardar a imagem de C# para voltar).
- O modo `?ao-vivo` foi verificado com um `aovivo.json` de amostra (o serviço de verdade precisa de rede e leva minutos para o baseline); o formato é o mesmo.

### Diferenças de comportamento (todas pequenas e propositais)

- `criadaEmUtc` sai sempre com `Z` (o C# omitia o `Z` no histórico, o que faz o JavaScript ler a hora como local).
- Histórico: "1 previsão guardada" / "N previsões guardadas" (o Razor dizia "1 previsão guardadas").
- Linhas vazias do feed são botões desabilitados e fora do Tab (antes eram botões focáveis sem efeito).
- Em `/api/*`, caminho que não existe devolve o 404 padrão do Go, e método errado, 405 com `Allow`.
- Como a `index.html` é uma só para o mapa, `/testar` e `/historico`, o `preload` do mapa-base saiu (ele só valia para o mapa).
