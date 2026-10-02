# AGENTS.md

Instructions for AI agents working in this repository (Claude Code loads it through `CLAUDE.md`).

## Project

Projeto acadêmico (grupo 16): classificar o estado de rotas de rede em **OK / RISCO / FALHA** a partir de
medições públicas de ping do RIPE Atlas, com uma árvore de decisão. O "normal" de cada rota é aprendido dela
mesma, então o modelo usa métricas **relativas ao baseline de cada fluxo**, não limites fixos em ms.

Estágio atual: o pipeline segue a arquitetura medalhão (`SPEC-medalhao.md`): Bronze (cópia do BigQuery),
Silver (normalização) e o Gold (cálculo do X: baseline + features; cálculo do Y: rótulo OK / RISCO / FALHA em
`src/preditor/gold/calculo_y/`, spec em `SPEC-calculo-y.md`) estão prontos. A árvore inicial (Tarefa 3) também:
código em `src/preditor/modelo/`, spec em `SPEC-arvore.md`. A visualização (replay da validação num mapa-múndi)
também: exportador em `src/preditor/visualizacao/`, página em `web/`, spec em `SPEC-visualizacao.md`. O ajuste da
árvore (Tarefa 4) e o teste único (Tarefa 5) vêm depois.

A pergunta, as regras de rótulo e a origem dos dados estão em `docs/` (índice em `docs/README.md`; a RFC em
`docs/projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md` é a referência das fórmulas, §8.2 a §8.4).

## Stack

- Python 3.11, gerenciado com `uv` (build backend `uv_build`, pacote `preditor` em `src/`).
- PySpark 3.5 em modo local; só a camada Bronze lê do BigQuery, via conector Spark (baixado na primeira execução).
  O Spark fica só no pipeline de dados (Bronze → Gold).
- A árvore (`src/preditor/modelo/`) usa scikit-learn (`DecisionTreeClassifier`), lendo o Gold com pandas + pyarrow:
  `scikit-learn`, `pandas` e `pyarrow` são dependências do pacote. Sem Spark e sem Java.
- Java 17 (exigido pelo Spark) e `gcloud auth application-default login` para as credenciais do BigQuery (só o Bronze).
- Fonte: tabela `atlas-ripe-509700.atlasRipe.atlas`, região EU.
- Notebooks (grupo `notebook`: `requests`, `pandas`, `ipykernel`) usam a API do RIPE Atlas diretamente; `pandas`
  aparece nos dois lugares porque o grupo é separado das dependências do pacote.
- A página (`web/`) é HTML + CSS + JavaScript puro em módulos ES, sem framework, sem build e sem CDN: D3, TopoJSON e o
  contorno do mundo ficam em `web/vendor/` (origem, versão e licença no README de lá). O exportador e o servidor usam
  só pandas, scikit-learn e a biblioteca padrão.
- Sem framework de testes, linter ou type-checker configurados.

## Commands

```bash
# install:
uv sync
# install (notebooks):
uv sync --group notebook
# run (pipeline completo: bronze → silver → gold):
uv run python -m preditor
# run (uma camada; cada uma lê a anterior do disco):
uv run python -m preditor bronze   # BigQuery → data/bronze/ (rede + gcloud)
uv run python -m preditor silver   # data/bronze/ → data/silver/ (offline)
uv run python -m preditor gold     # data/silver/ → data/gold/ (offline; inclui dataset_rotulado_B.parquet
                                   # e contagem_classes.csv)
# run (a árvore; comando à parte, não entra na execução sem argumento):
uv run python -m preditor arvore   # data/gold/ → data/modelo/ (offline, sem Spark nem Java)
# run (a visualização; comandos à parte, offline, sem Spark nem Java):
uv run python -m preditor replay   # data/gold/ → web/dados/replay.json (refaz a árvore oficial)
uv run python -m preditor servir   # serve web/ em http://127.0.0.1:8000/ (--porta N); não use `python -m http.server`
uv run python -m preditor.visualizacao.coletar_sondas   # só para refazer sondas.csv (rede: API pública do RIPE Atlas)
# typecheck: não há
# lint: não há
# test: não há — a verificação é rodar o pipeline; cada camada termina com checagens automáticas
#       (Bronze: linhas e colunas = BigQuery; Silver: nenhum rtt <= 0, nenhum par (fluxo_id, t) repetido, 82 fluxos;
#        Gold: Período A não vaza para as features, 81 fluxos no baseline, 2 insuficientes; rótulo: mesmas linhas
#        das features, regra ↔ classe, FALHA com precedência, status_futuro conferido por um caminho independente
#        do lead, blocos em ordem de tempo, cada bloco com as 3 classes. O gold imprime também 3 exemplos reais;
#        Árvore: X com exatamente as 8 colunas e nenhuma proibida, nenhum futuro nulo, nenhuma das 3 últimas medições
#        de um fluxo em treino ou validação, 3 classes em treino e validação, `fit` só com o treino, matriz soma o N da
#        validação e F1 macro = média dos 3 F1 da matriz, a escolhida é a 1ª linha da busca, regras só com colunas
#        permitidas e cada regra seleciona exatamente as linhas da folha, mesma semente = mesma árvore, nenhuma
#        linha do teste medida. Ela imprime também os resultados para o diário;
#        Replay: árvore refeita = `arvore_oficial.json`, nenhuma linha nem instante do teste no JSON, conferíveis = N da
#        validação, matriz e F1 recalculados do JSON = CSVs da árvore, `t_futuro` conferido por caminho independente,
#        `x` só com as 8 colunas e ausente continua ausente, cada regra seleciona exatamente as linhas da folha, toda
#        rota começa na sonda, termina no destino e só usa cabo do catálogo, mesma semente = mesmo JSON. A página se
#        confere abrindo: ao fim do replay o placar e a matriz são iguais aos CSVs)
```

Só `bronze` (e o pipeline completo) precisa de rede e credenciais do BigQuery. `silver` e `gold` rodam offline, mas
exigem a camada anterior no disco: sem ela, terminam com a mensagem de qual comando rodar antes (nunca recaem no
BigQuery). `arvore` também roda offline e exige o Gold (sem ele, pede `uv run python -m preditor gold`). Sem rede,
verifique ao menos a importação: `uv run python -c "import preditor.__main__"`. `replay` exige o Gold, as saídas do
`arvore` e o `sondas.csv`; `servir` exige o `replay.json` (cada um diz qual comando rodar antes).

## Conventions

- Código, nomes, comentários e docs em português (ex.: `calculo_x`, `baseline_insuficiente`, `fluxo_id`).
- Cada camada do pipeline fica em sua pasta: `bronze/` → `silver/` → `gold/` (o Gold tem `calculo_x/` e `calculo_y/`
  dentro); `__main__.py` orquestra, grava e verifica. Cada camada lê a anterior do disco, nunca da memória.
- A árvore fica em `modelo/`, fora do medalhão: `dados.py`, `avaliacao.py`, `arvore.py`, `regras.py` e `execucao.py`
  (orquestra, grava e verifica). Lê o Gold do disco com pandas, sem Spark.
- A visualização fica em `visualizacao/`, também fora do medalhão: `rotas.py`, `exportacao.py`, `execucao.py` (orquestra,
  verifica e só então grava), `servidor.py` e `coletar_sondas.py`. Ela reutiliza `modelo/` sem alterá-lo.
- A página fica em `web/`: `app.js` orquestra; `tempo.js` e `placar.js` são lógica pura (sem DOM, rodam em Node);
  `mapa.js`, `rotas.js`, `desenho.js`, `pulsos.js`, `selos.js` cuidam do mapa; `cartao.js`, `painel.js`, `foco.js` e
  `comum.js`, do painel. Sem `innerHTML` com dados; CSP `default-src 'self'`. As constantes só de desenho (durações,
  tamanhos) ficam no topo do módulo JS que as usa, comentadas, porque o JS não lê `config.py`.
- Todo "número mágico" vai para `src/preditor/config.py`, com comentário dizendo a origem (seção da RFC ou decisão).
- O código comenta cada passo, mas não repete a teoria da RFC: referencia a seção.
- Saídas vão para `data/{bronze,silver,gold}/` (ignoradas pelo git): Parquet para dados, CSV só para leitura humana.
  As da árvore vão para `data/modelo/` (também ignoradas): CSV, JSON e TXT para leitura. O `replay.json` vai para
  `web/dados/` (ignorada); `visualizacao/sondas.csv` e `web/vendor/` são versionados.
- O dono está começando em PySpark: prefira transformações legíveis e explicadas a construções compactas.

## Decisions

- **Dataset de 7 dias** (18/09 a 25/09/2026). Período A = primeiras **108 h** (menor corte em que todos os fluxos
  passam de 1.500 RTT válidos); Período B = o restante. As datas de corte da RFC são de uma coleta anterior.
- **RTT válido** = `rtt > 0` e `timeout = false` (no Atlas, timeout vem com `rtt = 0.0`).
- **RTT da medição** = média dos pings válidos da rajada; **jitter** = média de |Δrtt| entre pings consecutivos.
- **`fluxo_id` = `prb_id|dst_addr|msm_id`**: 81 fluxos no baseline (79 com baseline, 2 com `baseline_insuficiente`);
  o Silver tem 82 `fluxo_id`, o 82º só com medições no Período B, fora do modelo.
- **Arquitetura medalhão**: o Bronze copia a tabela inteira do BigQuery, sem filtro (lido uma vez); o Silver tem uma
  linha por medição; o Gold tem baseline, features, `limites_por_regiao.csv` e o dataset rotulado.
- **Duplicatas removidas no Silver** (`dropDuplicates()`): 63 linhas idênticas vindas da tabela de origem (9 no
  Período A, 54 no B). Sem isso a janela das "últimas 5" contava a medição duas vezes e a "3ª medição à frente"
  ficava ambígua. Com a remoção, `features_B` tem 70.616 linhas; os 82 / 81 / 2 fluxos e o corte A/B não mudam.
- **As checagens de contagem em `config.py`** (`FLUXOS_SILVER` = 82, `FLUXOS_BASELINE` = 81, `FLUXOS_INSUFICIENTES` = 2)
  valem para este dataset de 7 dias. Se a coleta for refeita, elas falham de propósito: revise-as junto com as decisões.
- **`status_atual`** = tabela da RFC §8.4 aplicada na ordem (a primeira linha verdadeira decide); a coluna `regra`
  (1 a 6) guarda qual linha disparou e a classe é derivada dela. O Y só lê colunas do X, não recalcula métrica.
- **Limitação conhecida da regra 3** (`z_robusto` ≥ 3,5, sem piso em ms nem em %): 88 % dessas FALHAs têm
  `aumento_pct` < 30 % (fluxos muito estáveis, com MAD pequeno). O dono decidiu seguir a regra da professora.
- **`status_futuro`** = `status_atual` da 3ª medição seguinte do mesmo fluxo, só se ela estiver de 600 a 840 s
  depois (RFC §3); senão é nulo. Linhas com futuro nulo ficam no dataset: o treino do preditor as descarta.
- **`bloco`** (treino / validacao / teste): dois instantes de corte globais, iguais para todos os fluxos, a 50 % e
  70 % do intervalo entre o menor e o maior `t` do dataset rotulado; sem sorteio e **sem folga entre blocos** (RFC
  §9). Em treino e validação, as 3 últimas medições de cada fluxo têm `status_futuro` vindo do bloco seguinte (a árvore
  as descarta: ver "Folga" abaixo); no teste, esse futuro é nulo (fim da série).
- **Região e país são metadados, não features**: a RFC proíbe usá-los na árvore.
- **Árvore: alvo `status_futuro`** (preditor de 12 min: com as métricas de agora, prevê a classe 3 medições à frente).
  Colunas = as 8 do diário da Tarefa 3: `z_robusto`, `aumento_pct`, `jitter_relativo`, `perda_pct`, `timeout_atual`,
  `n5_timeout`, `n5_aumento80`, `n5_moderado` (o `n5_risco` do diário é o `n5_moderado` do dataset). Fora, mesmo no
  dataset: `status_atual`, `regra`, `fluxo_id`, `rtt`, região, país e as demais colunas (lista em `config.py`).
- **Folga (RFC §9):** em treino e validação, descartam-se as 3 últimas medições de cada fluxo (o futuro delas está no
  bloco seguinte). Elas são marcadas no dataset inteiro, ordenado por `t`, **antes** de tirar as linhas com
  `status_futuro` nulo; na ordem inversa as "3 últimas" seriam outras linhas.
- **Valor ausente fica ausente:** X é `float64` com `NaN` e a árvore (scikit-learn ≥ 1.4) o aceita na divisão. Nada é
  imputado (RFC §8.3 proíbe trocar RTT ausente por 0).
- **Árvore: Gini, semente 16, `fit` só no treino.** Grade de 28 combinações (`max_depth` × `min_samples_leaf`); vence o
  maior F1 macro da validação, com desempate pela árvore mais simples (menor profundidade, depois folha maior).
- **Sem balanceamento de classes na Tarefa 3** (decisão do dono, 01/10/2026): fica para a Tarefa 4, medido contra esta
  árvore. **Comparação obrigatória com a persistência** ("o futuro é igual ao `status_atual`"), com as mesmas métricas
  na mesma validação; se a árvore não ganhar, registra-se assim, sem trocar alvo nem rótulo.
- **O teste fica fechado até a Tarefa 5:** `DadosModelo` nunca guarda linhas do teste (só o N) e `Avaliacao.medir`
  recusa esse bloco.
- **Árvore de contraste** (8 colunas + `rtt` + `destination_region`, mesmos hiperparâmetros): só mostra o que a árvore
  faz quando enxerga o RTT absoluto e a região. Não é o modelo do projeto e fica fora da entrega.
- **Regras em português** saem do caminho real raiz → folha de `tree_` (nada escrito à mão), com limiar de 4 casas e
  as condições repetidas do caminho fundidas por coluna (fica o limite mais apertado).
- **Contagens e métricas da árvore são resultado, não constantes:** N por bloco, hiperparâmetros escolhidos e F1 não
  ficam em `config.py` nem são checados contra um valor fixo; vêm da execução (referência em `tasks/todo-arvore.md`).
- **Visualização = replay, não medição ao vivo:** a página reproduz o bloco de **validação** (o teste continua fechado:
  o exportador recusa o bloco e nenhum instante do teste entra no JSON). O navegador não calcula métrica do X nem
  rótulo: só exibe, compara e soma campos do JSON. Trocar o bloco depois da Tarefa 5 exige rever as checagens de
  `visualizacao/execucao.py`.
- **Rota simulada, cabos reais:** o dataset é de ping, sem traceroute. Cada fluxo segue por terra até uma estação de
  aterragem, cruza por cabos que existem (catálogo à mão em `config.py`, 7 cabos conferidos na TeleGeography em
  01/10/2026; a geometria deles não é copiada) e termina por terra. A página avisa sempre que o caminho é ilustrativo.
- **Escolha da rota (confirmada pelo dono em 02/10/2026):** entre as opções do país, só entram as fisicamente possíveis
  (RTT mínimo teórico = 2 × km / 200 ≤ mediana do baseline do fluxo); a semente 16 + `fluxo_id` escolhe entre elas.
  O ponto do destino é por país: BR em Belo Horizonte (o único destino BR é um IP da UFMG); US em Miami ou Nova York,
  **inferido do RTT medido** (IP de localização desconhecida, provavelmente anycast).
- **Placar da página:** uma previsão só conta quando o relógio passa do instante do futuro (`t_futuro`); pular na barra
  de tempo dá o mesmo estado que tocar até lá. As medições sem futuro para conferir e as de folga ficam fora.
- **A árvore é refeita no `replay`** (mesma semente, conferida contra `arvore_oficial.json`): o `arvore` não grava o
  modelo treinado. As regras das 16 folhas vêm de `Regras._caminhos` (método privado de `modelo/regras.py`).
- **`servir` em vez de `python -m http.server`:** o servidor padrão (fila de 5 conexões, HTTP/1.0) perdia arquivos com
  vários navegadores ao mesmo tempo; o `servir` usa fila de 128 e HTTP/1.1, só em `127.0.0.1`.
- O baseline usa só o Período A; nada do Período A pode entrar nas features do Período B.
- Os notebooks `01`–`03` são entregas da primeira fase no formato pedido pela professora: fazem GET/POST na API do
  RIPE Atlas e não usam o BigQuery nem `src/preditor`. Não os migre para o pipeline.

## Security rules

- Nunca versionar credenciais: `RIPE_ATLAS_API_KEY` fica no ambiente ou em `.env` (ignorado pelo git); o BigQuery
  usa as credenciais padrão do gcloud, sem arquivo de chave no repositório.
- Não commitar dados de nenhuma camada (`data/raw/*`, `data/{bronze,silver,gold}/`), só os READMEs e docs.
- Não imprimir chaves ou tokens em logs, notebooks ou saídas de célula.

## Agent workflow

- Lifecycle: `/spec` → `/plan` → `/build` → `/verify` → `/review`. Specs live in the repo; the plan in `tasks/plan.md`, tasks in `tasks/todo.md` (the Y spec uses `tasks/plan-calculo-y.md` and `tasks/todo-calculo-y.md`; the tree spec, `SPEC-arvore.md`, uses `tasks/plan-arvore.md` and `tasks/todo-arvore.md`; the visualization spec,
  `SPEC-visualizacao.md`, uses `tasks/plan-visualizacao.md` and `tasks/todo-visualizacao.md`).
- Agents: `implementer` implements one task and stops for review; `reviewer` reviews the diff without editing.
- Skills live in `.claude/skills/` and belong to this project: adapt them freely. `.claude/catalog.md` lists catalog skills not installed yet.
- Do not commit or push without the owner asking.
