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
também: exportador em `src/preditor/visualizacao/`, página em `web/`, spec em `SPEC-visualizacao.md`; desde 10/10/2026 o replay prevê com a Random Forest exportada (spec em `SPEC-replay-floresta.md`). O ajuste da
árvore (Tarefa 4) também: `src/preditor/modelo/ajuste.py` e `execucao_ajuste.py`, spec em `SPEC-ajuste-arvore.md`,
análise em `docs/relatorio_analise_arvore.md`. O painel da árvore na página (spec em `SPEC-arvore-na-pagina.md`) existiu até 10/10/2026: a página foi
simplificada para público não técnico e ele saiu (ver "Página para público não técnico" em Decisions). O piso da regra 3 (10/10/2026) também: a linha 3 do Y exige
`aumento_pct` ≥ 30 % além de `z_robusto` ≥ 3,5; spec em `SPEC-piso-regra3.md`, com o antes × depois e a análise de
robustez na seção 8 de `docs/relatorio_analise_arvore.md`. A comparação com Random Forest e XGBoost (10/10/2026) também:
`floresta.py`, `boosting.py`, `comparacao.py` e `execucao_comparacao.py` em `src/preditor/modelo/`, spec em
`SPEC-comparacao-modelos.md`, relatório em `docs/relatorio_comparacao_modelos.md`. A regra entre famílias escolheu a
Random Forest, e o modelo foi exportado para `data/modelo/exportado/` (`exportacao.py`). O teste único (Tarefa 5) foi feito
em 10/10/2026: o teste foi aberto **uma vez** (spec em `SPEC-teste-final.md`; resultado em `docs/resultado_teste_final.md`;
ficha em `docs/ficha_modelo_final.md`).

A pergunta, as regras de rótulo e a origem dos dados estão em `docs/` (índice em `docs/README.md`; a RFC em
`docs/projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md` é a referência das fórmulas, §8.2 a §8.4).

## Stack

- Python 3.11, gerenciado com `uv` (build backend `uv_build`, pacote `preditor` em `src/`).
- PySpark 3.5 em modo local; só a camada Bronze lê do BigQuery, via conector Spark (baixado na primeira execução).
  O Spark fica só no pipeline de dados (Bronze → Gold).
- A árvore (`src/preditor/modelo/`) usa scikit-learn (`DecisionTreeClassifier`), lendo o Gold com pandas + pyarrow:
  `scikit-learn`, `pandas` e `pyarrow` são dependências do pacote. Sem Spark e sem Java.
- A comparação usa também `xgboost` (dependência do pacote; no macOS, `brew install libomp` antes) e `joblib` (vem com o
  scikit-learn). `uv add xgboost` foi rodado pela sessão principal em 10/10/2026.
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
# run (a árvore ajustada da Tarefa 4; comando à parte, offline, sem Spark nem Java):
uv run python -m preditor ajuste   # data/gold/ + saídas do `arvore` → data/modelo/ (não reescreve os arquivos da Tarefa 3)
# run (a visualização; comandos à parte, offline, sem Spark nem Java):
uv run python -m preditor replay   # data/gold/ + modelo_final.joblib → web/dados/replay.json (prevê com a Random Forest; sem treinar)
uv run python -m preditor servir   # serve web/ em http://127.0.0.1:8000/ (--porta N); não use `python -m http.server`
uv run python -m preditor.visualizacao.coletar_sondas   # só para refazer sondas.csv (rede: API pública do RIPE Atlas)
# run (a comparação Random Forest × XGBoost × árvore; comandos à parte, offline, sem Spark nem Java):
uv run python -m preditor comparar  # data/gold/ + saídas de arvore e ajuste → data/modelo/comparacao/ (~4 min)
uv run python -m preditor exportar  # escolha.json do comparar → data/modelo/exportado/ (.joblib, LEIA-ME.md, exemplo; ~10 s)
# run (o teste único, Tarefa 5; comandos à parte, offline, sem Spark nem Java; spec em SPEC-teste-final.md):
uv run python -m preditor teste --ensaio          # mesmo caminho do teste, nas linhas da VALIDAÇÃO; confere com o comparar e grava ensaio_ok.json
uv run python -m preditor teste --abrir-o-teste   # o teste foi aberto UMA vez em 10/10/2026, 14:49; recusa com carimbo inválido ou com TESTE_ABERTO.json
# run (análise do piso da regra 3; fora do pipeline, não grava no projeto; saídas em data/analise_piso_regra3/, ignorada pelo git):
uv run python data/analise_piso_regra3/robustez_piso.py      # antes × depois: ganho com IC por fluxo, dobra interna, pares (~3 min)
uv run python data/analise_piso_regra3/conferir_secao8.py    # confere cada número da seção 8 contra numeros_secao8.csv
JAVA_HOME=/opt/homebrew/opt/openjdk@17 uv run python data/analise_piso_regra3/conferir_rotulo_piso.py   # rótulo com piso None e 30, em memória (Spark)
# typecheck: não há
# lint: não há
# test: não há — a verificação é rodar o pipeline; cada camada termina com checagens automáticas
#       (Bronze: linhas e colunas = BigQuery; Silver: nenhum rtt <= 0, nenhum par (fluxo_id, t) repetido, 82 fluxos;
#        Gold: Período A não vaza para as features, 81 fluxos no baseline, 2 insuficientes; rótulo: mesmas linhas
#        das features, regra ↔ classe, FALHA com precedência, status_futuro conferido por um caminho independente
#        do lead, blocos em ordem de tempo, cada bloco com as 3 classes; piso da regra 3 (`PISO_AUMENTO_FALHA_PCT`):
#        nenhuma linha OK com z e aumento acima do piso, toda linha da regra 3 com z e aumento acima do piso, z e aumento
#        altos só nas regras 1 a 3, z alto com aumento abaixo do piso nunca na regra 3, e o gold imprime quantas medições
#        o piso tirou da regra 3 e para onde foram. O gold imprime também 3 exemplos reais;
#        Árvore: X com exatamente as 8 colunas e nenhuma proibida, nenhum futuro nulo, nenhuma das 3 últimas medições
#        de um fluxo em treino ou validação, 3 classes em treino e validação, `fit` só com o treino, matriz soma o N da
#        validação e F1 macro = média dos 3 F1 da matriz, a escolhida é a 1ª linha da busca, regras só com colunas
#        permitidas e cada regra seleciona exatamente as linhas da folha, mesma semente = mesma árvore, nenhuma
#        linha do teste medida. Ela imprime também os resultados para o diário;
#        Gold (histórico do z): `min5_z` ≤ `media5_z` e ≤ `z_robusto`, as duas conferidas por auto-junção (sem a janela),
#        nulas só quando nenhuma das 5 medições tem z;
#        Ajuste: X com exatamente as 10 colunas e nenhuma proibida, árvore da Tarefa 3 refeita = `arvore_oficial.json` e
#        métricas = `metricas_validacao.csv`, 56 combinações por variante, a escolhida é a mais simples dentro da
#        tolerância (conferida de novo a partir do CSV), matrizes somam o N da validação, regiões e transições somam o
#        total, regras só com as 10 colunas e cada regra seleciona exatamente as linhas da folha, mesma semente = mesma
#        árvore, nenhuma linha do teste medida;
#        Replay (SPEC-replay-floresta.md): bloco `modelo` = SHA-256 do LEIA-ME, família, árvores e colunas do `.joblib`; previsões do
#        JSON = as do modelo recarregado, linha a linha; matriz e F1 recalculados do JSON = linhas `random_forest` e `persistencia`
#        de `matriz_comparacao.csv` e `comparacao_modelos.csv` (F1 0,6977, N 13.490); `t_futuro` conferido por caminho independente;
#        nenhuma linha nem instante do teste no JSON; rotas começam na sonda, terminam no destino e só usam cabo do catálogo;
#        mesma entrada = mesmo JSON; o JSON não tem `arvores`, `folha`, `x` nem regras. A página se
#        confere abrindo: ao fim do replay o placar (acertos da floresta e do palpite simples) é igual ao do JSON e ao da comparação;
#        Comparação: as 5 linhas nas mesmas linhas da validação, `fit` só no treino, regra entre famílias refeita a partir
#        do CSV, IC pareado com 2.000 reamostras (mesma semente = mesmo IC), `Avaliacao` recusa o teste, árvores refeitas =
#        JSON e CSVs do `arvore` e do `ajuste`, duas execuções = mesmos arquivos (exceto `tempos.csv`);
#        Exportação: o `.joblib` reaberto em processo novo reproduz as previsões da validação, aceita NaN, só devolve
#        OK/RISCO/FALHA, não cita o pacote `preditor`, o exemplo roda de outra pasta, e o LEIA-ME traz o SHA-256 do arquivo)
```

Só `bronze` (e o pipeline completo) precisa de rede e credenciais do BigQuery. `silver` e `gold` rodam offline, mas
exigem a camada anterior no disco: sem ela, terminam com a mensagem de qual comando rodar antes (nunca recaem no
BigQuery). `arvore` também roda offline e exige o Gold (sem ele, pede `uv run python -m preditor gold`). Sem rede,
verifique ao menos a importação: `uv run python -c "import preditor.__main__"`. `ajuste` exige o Gold com as colunas novas e as saídas do `arvore`. `replay` exige o Gold, o `.joblib` e o LEIA-ME do `exportar`, as saídas do `comparar` e o `sondas.csv`; `servir` exige o `replay.json` (cada um diz qual comando rodar antes). `comparar` exige o Gold e as saídas do `arvore` e do
`ajuste`; `exportar` exige as saídas do `comparar`. `teste --ensaio` exige o `exportar` (o `.joblib` e o LEIA-ME);
`teste --abrir-o-teste` exige também o carimbo `ensaio_ok.json` válido (SHA-256 do modelo, da escolha e do código de
medição) e recusa se `TESTE_ABERTO.json` existir. Sem argumento, `teste` não roda.

## Conventions

- Código, nomes, comentários e docs em português (ex.: `calculo_x`, `baseline_insuficiente`, `fluxo_id`).
- Cada camada do pipeline fica em sua pasta: `bronze/` → `silver/` → `gold/` (o Gold tem `calculo_x/` e `calculo_y/`
  dentro); `__main__.py` orquestra, grava e verifica. Cada camada lê a anterior do disco, nunca da memória.
- A árvore fica em `modelo/`, fora do medalhão: `dados.py`, `avaliacao.py`, `arvore.py`, `regras.py` e `execucao.py`
  (orquestra, grava e verifica). Lê o Gold do disco com pandas, sem Spark.
- A árvore ajustada (Tarefa 4) fica ao lado, em `modelo/ajuste.py` e `modelo/execucao_ajuste.py`. Ela reutiliza
  `ArvoreBase`, `Regras` e `Avaliacao`; qualquer mudança nesses três precisa manter o `arvore` e o `ajuste` com
  saídas idênticas com o mesmo Gold (os parâmetros novos têm como padrão o comportamento da Tarefa 3). Com outro Gold
  as saídas mudam: o código não mudou, o dado sim.
- A comparação fica em `modelo/`, ao lado: `floresta.py` (Random Forest) e `boosting.py` (XGBoost) reutilizam `DadosModelo`
  e `Avaliacao` e a regra de escolha de `comparacao.py` (`escolher_por_regra`). `comparacao.py` é só cálculo (regra, IC,
  tabelas) e não importa `floresta` nem `boosting`. `execucao_comparacao.py` treina, verifica e grava; `exportacao.py`
  só grava o `.joblib` depois de abri-lo em processo novo. A árvore ajustada mantém a sua cópia da regra: `ajuste.py` não mudou.
- O teste único (Tarefa 5) também fica em `modelo/`: `dados_teste.py` lê um bloco do Gold (o teste só com
  `liberar_teste=True`; só `execucao_teste.py` o importa, conferido por `grep`), e `execucao_teste.py` orquestra o ensaio
  e a abertura (trava, carimbo, medição, checagens, gravação). Não altera `DadosModelo`.
- A visualização fica em `visualizacao/`, também fora do medalhão: `rotas.py`, `exportacao.py`, `execucao.py` (orquestra,
  verifica e só então grava), `modelo_exportado.py` (lê o `.joblib` com as mesmas conferências do `teste`, por cópia: `execucao_teste.py` carrega o bloco de teste e não é importado), `servidor.py` e `coletar_sondas.py`. Ela reutiliza `modelo/` sem alterá-lo.
- A página fica em `web/`: `app.js` orquestra; `tempo.js` e `placar.js` são lógica pura (sem DOM, rodam em Node);
  `mapa.js`, `rotas.js`, `desenho.js`, `pulsos.js`, `selos.js` cuidam do mapa; `cartao.js`, `painel.js`, `foco.js` e
  `comum.js`, do painel (`comum.js` também guarda os nomes na tela: Normal / Atenção / Problema, países por extenso). Sem `innerHTML` com dados; CSP `default-src 'self'`. As constantes só de desenho (durações,
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
- **Piso na regra 3 (decidido em 09/10/2026, `SPEC-piso-regra3.md`):** a linha 3 do Y exige `z_robusto` ≥ 3,5 **e**
  `aumento_pct` ≥ `PISO_AUMENTO_FALHA_PCT` (30; `None` = a regra da RFC ao pé da letra). Motivo: no rótulo anterior, 88 %
  das FALHAs da regra 3 tinham `aumento_pct` < 30 % (fluxos muito estáveis, com MAD pequeno). O 30 é o limite de RISCO
  por aumento da própria tabela (RFC §8.4, linha 5), não um valor varrido na validação. Só a linha 3 mudou: o X é o
  mesmo, e 14.370 medições saíram da regra 3 (11.436 para OK, 2.929 para RISCO, 5 para FALHA). Resultados e ressalvas
  na seção 8 do relatório. A análise antes × depois fica em `data/analise_piso_regra3/` (ignorada pelo git).
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
- **Teste aberto em 10/10/2026, uma vez (14:49:21 a 14:49:23):** o bloco de teste foi medido pelo `teste --abrir-o-teste`,
  com o carimbo `ensaio_ok.json` válido e a trava `TESTE_ABERTO.json` gravada em `em_andamento` **antes** da leitura. A
  trava está `concluido` e **não se apaga pelo código**: uma segunda abertura é recusada. Nada foi retreinado, reajustado
  nem re-escolhido por causa do teste. Resultado e declaração em `docs/resultado_teste_final.md`; ficha em
  `docs/ficha_modelo_final.md`.
- **Teste: só a abertura lê o bloco.** `DadosModelo` nunca guarda linhas do teste (só o N), e `Avaliacao.medir` e
  `quando_muda` recusam o bloco de teste sem `liberar_teste=True`. Só `execucao_teste.py` importa `dados_teste.py`.
- **Teste: a declaração segue a regra da spec.** "Preditor de 12 minutos" só se o limite inferior do IC 95 % do ganho de
  F1 macro sobre a persistência for maior que zero (leitura do dono, 10/10/2026; `SPEC-teste-final.md`, regra 4). No teste,
  o limite inferior foi +0,0168: declarado preditor, com prova fraca.
- **Teste: o que foi medido.** Só a Random Forest escolhida e a persistência (`modelo_final.joblib`, SHA-256 conferido
  contra o LEIA-ME). A árvore ajustada e o XGBoost não foram medidos no teste.
- **Árvore de contraste** (8 colunas + `rtt` + `destination_region`, mesmos hiperparâmetros): só mostra o que a árvore
  faz quando enxerga o RTT absoluto e a região. Não é o modelo do projeto e fica fora da entrega.
- **Regras em português** saem do caminho real raiz → folha de `tree_` (nada escrito à mão), com limiar de 4 casas e
  as condições repetidas do caminho fundidas por coluna (fica o limite mais apertado).
- **Contagens e métricas da árvore são resultado, não constantes:** N por bloco, hiperparâmetros escolhidos e F1 não
  ficam em `config.py` nem são checados contra um valor fixo; vêm da execução (referência em `tasks/todo-arvore.md`).
- **Ajuste da árvore (Tarefa 4, 02/10/2026): as duas árvores ficam.** A da Tarefa 3 não muda em nada; a ajustada é
  medida contra ela e contra a persistência, nas mesmas linhas. O `replay` continua na árvore da Tarefa 3.
- **Colunas novas do ajuste:** `min5_z` e `media5_z` (menor e média do `z_robusto` nas últimas 5 medições do fluxo,
  mesma janela das `n5_`, nulo ignorado). Nascem no Gold e ficam em `COLUNAS_AJUSTE`: `COLUNAS_ARVORE` continua com as
  8, e cada coluna do Gold está em exatamente uma das três listas (árvore, ajuste, proibidas).
- **Escolha da ajustada:** grade da Tarefa 3 × {Gini, entropia}; entre as árvores a até 0,005 do melhor F1 macro da
  validação, vence a mais simples (menor `max_depth`, depois folha mínima maior, depois Gini). O maior F1 puro levaria
  a 187 folhas por +0,004 (rótulo anterior ao piso).
- **Peso de classe {OK 1, RISCO 2, FALHA 1,5}:** revê a decisão de 01/10 (sem balanceamento na Tarefa 3, que
  continua valendo para a árvore da Tarefa 3). O diário da Tarefa 4 não lista peso entre os ajustes permitidos: as
  duas variantes são medidas e gravadas, a adotada é a com peso. A professora liberou pesos de classe (relato do dono,
  09/10/2026). Em 10/10/2026, com o rótulo do piso, a varredura de 32 combinações (`data/analise_piso_regra3/`) não
  achou nenhuma que ganhe mais de 0,005 de F1 macro nas duas medidas; o peso fica. Se a professora vetar, troca-se
  `MODELO_AJUSTADA` em `config.py`. O registro no diário da Tarefa 4 é do dono.
- **Recall e precisão de FALHA (rótulo anterior ao piso):** na ajustada com peso, o recall era 0,754 e a precisão 0,910,
  contra 0,779 e 0,846 da oficial. Com o piso (seção 8.3 do relatório), a ajustada com peso tem recall 0,505 e precisão
  0,643. A regra de escolha não exige o recall, e a seção 8.5 lista a queda como ressalva medida.
- **Regras em português da ajustada com 6 casas no limiar** (`CASAS_LIMIAR_REGRA_AJUSTE`): com as 4 da Tarefa 3, o
  limiar impresso selecionava outras linhas. Com peso, `Regras.verificar` desconta o peso de `tree_.value` na pureza.
- **Teto conhecido dos dados (rótulo anterior ao piso; não refeito com o piso, seção 8.5 do relatório):** nem um boosting de 300 árvores com 20 colunas passa de 0,77 de F1 macro, nem de 13 %
  de acerto em OK → FALHA; 68 % dos episódios de FALHA duram uma medição (regra 3). Antecipar o início de uma falha a
  12 min não é possível com estas medições (relatório, seção 7). Não insistir em hiperparâmetro.
- **Visualização = replay, não medição ao vivo:** a página reproduz o bloco de **validação** (o teste foi aberto em
  10/10/2026, mas a página segue na validação: o exportador recusa o bloco de teste e nenhum instante dele entra no JSON). O navegador não calcula métrica do X nem
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
- **[Substituída em 10/10/2026: ver a decisão da Random Forest no replay.] A árvore era refeita no `replay`** (mesma semente, conferida contra `arvore_oficial.json`): o `arvore` não grava o
  modelo treinado. As regras das folhas vêm de `Regras._caminhos` (método privado de `modelo/regras.py`).
- **Página para público não técnico (10/10/2026, dono):** `web/index.html` foi substituída por uma versão sem árvore, sem
  matriz de confusão e sem colunas do X, folha ou regra no cartão; os termos técnicos viraram palavras comuns (OK / RISCO /
  FALHA = Normal / Atenção / Problema; fluxo = conexão; sonda = ponto de medição; RTT = tempo de resposta; persistência =
  palpite simples). Só o texto da tela mudou: o JSON, o exportador e o CSS das classes seguem com os códigos do projeto,
  e, desde a Random Forest (10/10/2026), o `replay` não exporta mais `arvores`, `folha`, `x` nem regras. O placar mantém a comparação com o palpite simples.
  `arvore.js` e `caminho.js` saíram de `web/`; o painel da árvore abaixo ficou só no histórico (git).
- **Painel da árvore (03/10/2026, removido da página em 10/10/2026):** mostra a oficial e a ajustada (seletor), mas o seletor muda só o painel: mapa,
  cartão e placar seguem a oficial. O navegador não percorre a árvore com o X: recebe a folha do JSON e sobe pelos pais.
  Por isso o `replay` agora também exige as saídas do `ajuste` (superado em 10/10/2026: o `replay` não exige mais o `ajuste`).
- **Replay com a Random Forest (10/10/2026, `SPEC-replay-floresta.md`, aprovada pelo dono):** o `previsto` do replay vem do
  `modelo_final.joblib` exportado, que prevê a validação inteira (as medições sem futuro para conferir também). O arquivo é
  conferido contra o SHA-256 do LEIA-ME antes de abrir, e o placar contra `comparacao/matriz_comparacao.csv` e
  `comparacao_modelos.csv` (F1 macro 0,6977; N = 13.490). O JSON perdeu `arvores`, `colunas`, `regras`, `folha`, `x`,
  `folha_ajustada`, `previsto_ajustada` e `x_ajuste` (a página não os usava) e ganhou o bloco `modelo` (nome, família,
  árvores, parâmetros, SHA-256, colunas). O `replay` não refaz mais a árvore nem a ajustada (~4 s; a spec estimava ~50 s) e
  exige as saídas do `exportar` e do `comparar`. A página mostra "Random Forest, 100 árvores" (com `textContent`) e diz que o
  período é o de validação; o número do relatório é o do teste, que segue fechado no replay.
- **Constantes herdadas sem uso (10/10/2026):** `CASAS_X_REPLAY` e `CASAS_LIMIAR_REPLAY` (`config.py`) não são mais lidas pelo replay;
  ficam por não mexer em `config.py`, que faz parte do código de medição do teste (o carimbo `ensaio_ok.json` guarda o hash dele).
- **Desenho do painel com o piso (10/10/2026):** largura proporcional ao número de folhas (80 por folha, mínimo de
  1280 px), com rolagem horizontal que traz a folha em foco para a tela. Com o piso, a oficial tem 29 folhas e a
  ajustada, 40 (`SPEC-arvore-na-pagina.md`).
- **`servir` em vez de `python -m http.server`:** o servidor padrão (fila de 5 conexões, HTTP/1.0) perdia arquivos com
  vários navegadores ao mesmo tempo; o `servir` usa fila de 128 e HTTP/1.1, só em `127.0.0.1`.
- **Comparação das famílias (10/10/2026, `SPEC-comparacao-modelos.md`):** Random Forest (32 combinações) e XGBoost (16)
  usam o mesmo X da árvore ajustada (10 colunas), o peso de classe da ajustada adotada e a semente 16; treino só no treino,
  sem `early_stopping`. A escolha entre famílias é a regra da Tarefa 4 (a até 0,005 do maior F1 macro da validação; vence
  a mais simples: árvore, depois Random Forest, depois XGBoost). **Escolhida: Random Forest** (F1 macro 0,6977; o XGBoost
  tem 0,7006, dentro da tolerância, e o IC da diferença cruza o zero). A regra decide, não o maior F1. O IC pareado por fluxo
  (2.000 reamostras, semente 16) é gravado e não decide.
- **Tempos fora dos CSVs da comparação:** `tempos.csv` é gravado à parte e fica fora da checagem de arquivos iguais; os
  demais arquivos de `data/modelo/comparacao/` saem iguais em duas execuções.
- **Exportação (`exportar`):** o `.joblib` é um pickle, e abrir um pickle executa código. O LEIA-ME traz o SHA-256 e o
  aviso. O arquivo não cita o pacote `preditor`, e a reabertura em processo novo reproduz as previsões da validação. Se
  uma checagem falhar, nada vai para `data/modelo/exportado/`, que o git ignora.
- O baseline usa só o Período A; nada do Período A pode entrar nas features do Período B.
- Os notebooks `01`–`03` são entregas da primeira fase no formato pedido pela professora: fazem GET/POST na API do
  RIPE Atlas e não usam o BigQuery nem `src/preditor`. Não os migre para o pipeline.

## Security rules

- Nunca versionar credenciais: `RIPE_ATLAS_API_KEY` fica no ambiente ou em `.env` (ignorado pelo git); o BigQuery
  usa as credenciais padrão do gcloud, sem arquivo de chave no repositório.
- Não commitar dados de nenhuma camada (`data/raw/*`, `data/{bronze,silver,gold}/`), só os READMEs e docs.
- Não imprimir chaves ou tokens em logs, notebooks ou saídas de célula.

## Agent workflow

- Replay com a Random Forest: `SPEC-replay-floresta.md`, com `tasks/plan-replay-floresta.md` e `tasks/todo-replay-floresta.md`.
- Lifecycle: `/spec` → `/plan` → `/build` → `/verify` → `/review`. Specs live in the repo; the plan in `tasks/plan.md`, tasks in `tasks/todo.md` (the Y spec uses `tasks/plan-calculo-y.md` and `tasks/todo-calculo-y.md`; the tree spec, `SPEC-arvore.md`, uses `tasks/plan-arvore.md` and `tasks/todo-arvore.md`; the visualization spec,
  `SPEC-visualizacao.md`, uses `tasks/plan-visualizacao.md` and `tasks/todo-visualizacao.md`; the Tarefa 4 spec,
  `SPEC-ajuste-arvore.md`, uses `tasks/plan-ajuste-arvore.md` and `tasks/todo-ajuste-arvore.md`; the piso spec, `SPEC-piso-regra3.md`, uses
  `tasks/plan-piso-regra3.md` and `tasks/todo-piso-regra3.md`; the comparison spec, `SPEC-comparacao-modelos.md`, uses
  `tasks/plan-comparacao-modelos.md` and `tasks/todo-comparacao-modelos.md`; the teste spec, `SPEC-teste-final.md`, uses
  `tasks/plan-teste-final.md` and `tasks/todo-teste-final.md`).
- Agents: `implementer` implements one task and stops for review; `reviewer` reviews the diff without editing.
- Skills live in `.claude/skills/` and belong to this project: adapt them freely. `.claude/catalog.md` lists catalog skills not installed yet.
- Do not commit or push without the owner asking.
