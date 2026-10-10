# Preditor de falhas ML

Projeto acadêmico: classificar o estado de rotas de rede (**OK / RISCO / FALHA**)
a partir de medições públicas de ping do RIPE Atlas, com uma árvore de decisão.

O "normal" de cada rota é aprendido dela mesma: 110 ms é saudável em
Brasil → EUA e seria dez vezes o normal em Brasil → Brasil. Por isso o modelo
usa métricas **relativas ao baseline de cada fluxo**, e não limites fixos em ms.

A pergunta, as regras de rótulo e a origem dos dados estão em [`docs/`](docs/README.md).
Este README cobre só o código: como rodar e o que ele produz.

## Organização do repositório

| Pasta | O que é |
|---|---|
| `src/preditor/` | Código-fonte do projeto: o pipeline de dados em PySpark e a árvore de decisão em scikit-learn (`modelo/`) |
| `docs/` | Documentação acadêmica e dos dados, com índice em [`docs/README.md`](docs/README.md) |
| `notebooks/` | Entregas da primeira fase, no formato pedido pela professora: 01 (GET) e 02 (POST) direto na API do RIPE Atlas, 03 (rótulo `status_real` por limiar fixo). Não usam o BigQuery nem `src/preditor` |
| `data/{bronze,silver,gold}/` | Saídas de cada camada do pipeline (ignoradas pelo git) |
| `data/modelo/` | Saídas da árvore de decisão (ignoradas pelo git) |

## Ambiente

Pré-requisitos:

- [uv](https://docs.astral.sh/uv/): gerencia Python 3.11 e as dependências (`pyspark` 3.5; `scikit-learn`, `pandas` e
  `pyarrow` para a árvore).
- **Java 17**, exigido pelo Spark (só o pipeline de dados; o comando `arvore` roda sem Java):

  ```bash
  brew install openjdk@17
  echo 'export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home' >> ~/.zshrc
  ```

  Se o `java` não estiver no PATH (o `openjdk@17` do Homebrew fica instalado mas não
  linkado), exporte o `JAVA_HOME` acima antes de rodar o pipeline.

- **gcloud autenticado** (só para a camada Bronze): o conector do BigQuery usa as
  credenciais padrão, sem arquivo de chave.

  ```bash
  gcloud auth application-default login
  ```

Instalação:

```bash
uv sync
```

Os notebooks usam um grupo de dependências separado (`requests`, `pandas`,
`ipykernel`) e a chave `RIPE_ATLAS_API_KEY` no ambiente ou em `.env`:

```bash
uv sync --group notebook
```

## Executar

O pipeline segue a arquitetura medalhão: três camadas, cada uma gravada em disco e
lida pela seguinte (detalhes em [`SPEC-medalhao.md`](SPEC-medalhao.md)).

```bash
uv run python -m preditor          # bronze → silver → gold
uv run python -m preditor bronze   # lê o BigQuery e grava data/bronze/ (rede e gcloud)
uv run python -m preditor silver   # lê o Bronze do disco e grava data/silver/ (offline)
uv run python -m preditor gold     # lê o Silver do disco e grava data/gold/ (offline)
```

Só o `bronze` precisa de rede e de credenciais. Na primeira execução o Spark baixa o
conector do BigQuery, o que leva alguns minutos. `silver` e `gold` rodam offline, mas
precisam da camada anterior no disco: sem ela, terminam dizendo qual comando rodar antes.

| Camada | Arquivo | Uma linha por | Conteúdo |
|---|---|---|---|
| Bronze | `data/bronze/atlas.parquet` | medição bruta | Cópia fiel de `atlas-ripe-509700.atlasRipe.atlas` (região EU), sem filtro, com `pings` aninhado |
| Silver | `data/silver/medicoes.parquet` | medição | `fluxo_id`, metadados da rota, `rtt`, `jitter`, `perda_pct` e `periodo` (A ou B); linhas duplicadas da tabela de origem são removidas |
| Gold | `data/gold/baseline_por_fluxo.parquet` | fluxo | Ficha do Período A: mediana, MAD, IQR, jitter e perda típicos, taxa de resposta, `baseline_insuficiente` |
| Gold | `data/gold/features_B.parquet` | medição do Período B | O **X** do modelo: `latencia_relativa`, `aumento_pct`, `z_robusto`, `jitter_relativo`, `n5_*`, `tendencia`, `persistencia`, e o histórico do z nas últimas 5 medições (`min5_z`, `media5_z`), que só a árvore ajustada usa |
| Gold | `data/gold/limites_por_regiao.csv` | rota / país | Os limiares da regra traduzidos para ms, por região (só para leitura) |
| Gold | `data/gold/dataset_rotulado_B.parquet` | medição do Período B | O X (`features_B`) mais o **Y**: `regra` (1 a 6, a linha da tabela da RFC §8.4 que decidiu), `status_atual` (OK / RISCO / FALHA), `status_futuro` (o `status_atual` da 3ª medição à frente, 12 min depois; nulo se não existir ou houver lacuna) e `bloco` (treino / validacao / teste, por dois cortes de tempo iguais para todos os fluxos) |
| Gold | `data/gold/contagem_classes.csv` | bloco | N de cada bloco por classe, com início, fim e os dois instantes de corte (só para leitura) |

Cada camada termina com checagens automáticas: o Bronze tem as mesmas linhas e colunas
do BigQuery; o Silver não tem `rtt <= 0` (nenhum timeout entra como RTT válido), não repete
nenhum par (`fluxo_id`, `t`) e tem 82 fluxos; no Gold, o Período A não pode vazar para as
features, o baseline tem 81 fluxos (2 insuficientes) e o dataset rotulado tem as mesmas
linhas das features, com `regra` e `status_atual` coerentes, `status_futuro` conferido por
um caminho independente e os blocos em ordem de tempo, cada um com as três classes. Essas
contagens valem para o dataset de 7 dias atual: se a coleta for refeita, as checagens falham
de propósito (ver `src/preditor/config.py`). O Gold também imprime os fluxos excluídos, a
contagem por classe e três exemplos reais (um OK, um RISCO e um FALHA) para o diário.

### Árvore de decisão

A árvore inicial (Tarefa 3, spec em [`SPEC-arvore.md`](SPEC-arvore.md)) é um comando à parte: lê o Gold do disco com
pandas e treina com scikit-learn. Roda offline, sem Spark e sem Java, e **não** entra na execução sem argumento.

```bash
uv run python -m preditor arvore   # lê data/gold/ e grava data/modelo/ (offline)
```

Ela prevê a classe do mesmo fluxo 12 minutos à frente (`status_futuro`) com 8 métricas relativas ao baseline, e é
medida na validação ao lado da persistência ("o futuro é igual ao `status_atual`"). Sem o Gold no disco, termina
dizendo para rodar `uv run python -m preditor gold` antes. O bloco de teste fica fechado: aparece só como N.

| Arquivo em `data/modelo/` | Conteúdo |
|---|---|
| `busca_hiperparametros.csv` | As 28 combinações de `max_depth` × `min_samples_leaf`, com o F1 macro de treino e de validação; a primeira linha é a escolhida |
| `arvore_oficial.json` | Critério, hiperparâmetros pedidos e obtidos, folhas, semente e as 8 colunas |
| `regras_arvore_oficial.txt` | A árvore inteira em texto e as 3 regras em português, com N e pureza |
| `matriz_validacao.csv` | Matriz 3×3 em contagem na validação (linha = verdadeiro, coluna = previsto): persistência, árvore oficial e árvore de contraste |
| `metricas_validacao.csv` | Precisão, recall e F1 por classe, F1 macro, balanced accuracy e acurácia, dos mesmos três modelos |
| `regras_arvore_contraste.txt` | A árvore de contraste em texto (8 colunas + `rtt` + região); não é o modelo e fica fora da entrega |

Ao terminar, o comando confere por conta própria o que foi gravado (X só com as 8 colunas, nenhuma das 3 últimas
medições de um fluxo em treino ou validação, `fit` só com o treino, a matriz soma o N da validação, cada regra em
português seleciona exatamente as linhas da folha, mesma semente dá a mesma árvore) e imprime os resultados para o
diário: N por bloco e classe, a busca, as divisões dos dois primeiros níveis, as matrizes, árvore × persistência, as
3 regras e dois erros concretos.

### Árvore ajustada (Tarefa 4)

O ajuste (spec em [`SPEC-ajuste-arvore.md`](SPEC-ajuste-arvore.md), análise em
[`docs/relatorio_analise_arvore.md`](docs/relatorio_analise_arvore.md)) também é um comando à parte, offline, sem Spark
e sem Java. A árvore da Tarefa 3 **não muda**: a ajustada nasce ao lado e é medida contra ela.

```bash
uv run python -m preditor ajuste   # lê data/gold/ e as saídas do `arvore`; grava data/modelo/ (offline)
```

Ela usa as 8 colunas da Tarefa 3 mais duas do Gold, `min5_z` e `media5_z` (o menor e a média do `z_robusto` nas
últimas 5 medições do fluxo). A busca roda a grade da Tarefa 3 com Gini e entropia, em duas variantes: sem peso de
classe e com o peso {OK 1, RISCO 2, FALHA 1,5}. Entre as árvores a até 0,005 do melhor F1 macro da validação, vence a
mais simples. A variante adotada é a com peso (`MODELO_AJUSTADA` em `config.py`). Exige o Gold com as colunas novas
e as saídas do `arvore`; sem eles, diz qual comando rodar antes.

| Arquivo em `data/modelo/` | Conteúdo |
|---|---|
| `busca_ajuste.csv` | As 56 combinações de cada variante, com o F1 macro de treino e de validação e a escolhida marcada |
| `arvore_ajustada.json` | Critério, hiperparâmetros, folhas, semente, peso de classe e as 10 colunas da variante adotada |
| `regras_arvore_ajustada.txt` | A árvore ajustada inteira em texto e as 3 regras em português |
| `matriz_ajuste.csv` | Matriz 3×3 na validação: persistência, árvore da Tarefa 3 e as duas variantes |
| `metricas_ajuste.csv` | As métricas de sempre, mais o acerto quando o futuro muda, por transição (agora → futuro) e o F1 macro por região |
| `comparacao_t3_t4.csv` | A tabela do diário: folhas, F1 macro, recall de FALHA e de RISCO, acerto quando o futuro muda |

O comando confere o que gravou (X com exatamente as 10 colunas, a árvore da Tarefa 3 refeita igual a
`arvore_oficial.json`, a escolhida é a mais simples dentro da tolerância, as matrizes somam o N da validação, regiões
e transições somam o total, cada regra seleciona as linhas da folha, mesma semente dá a mesma árvore) e imprime o
material do diário da Tarefa 4. Os arquivos da Tarefa 3 não são reescritos.

### Visualização (replay no mapa-múndi)

Uma página web reproduz o bloco de validação em tempo acelerado (spec em
[`SPEC-visualizacao.md`](SPEC-visualizacao.md)): cada medição vira um pulso que vai da sonda ao destino e volta, a
árvore prevê a classe 12 minutos à frente e, quando esse futuro chega, a página mostra se acertou. São dois comandos,
os dois offline, sem Spark e sem Java:

```bash
uv run python -m preditor replay   # lê data/gold/, refaz as duas árvores e grava web/dados/replay.json
uv run python -m preditor servir   # serve a página em http://127.0.0.1:8000/ (--porta N troca a porta)
```

Use o `servir`, não o `python -m http.server`: a página carrega vários módulos ao mesmo tempo e o servidor padrão do
Python perde arquivos quando mais de um navegador abre a página.

O que é real e o que é simulado: as medições, os rótulos e as previsões vêm do Gold e da árvore oficial; os cabos
submarinos existem (conferidos no mapa da TeleGeography), mas **o caminho de cada fluxo por eles é simulado**, porque
o dataset é de ping e não tem traceroute. A página mantém esse aviso sempre visível.

Na página: tocar / pausar (ou Espaço), velocidades de 60×, 300× e 900×, barra de tempo, filtro por região, placar da
árvore ao lado da persistência, matriz 3×3 e as últimas conferências. Clicar num selo do mapa ou numa linha do feed
abre o cartão do fluxo: rota, km, RTT mínimo teórico ao lado da mediana real, as 8 colunas que a árvore viu e a regra
em português da folha. Ao fim do replay, o placar e a matriz são iguais aos de `metricas_validacao.csv` e
`matriz_validacao.csv`.

Abaixo do mapa fica o painel da árvore (spec em [`SPEC-arvore-na-pagina.md`](SPEC-arvore-na-pagina.md)): o diagrama com
todos os nós de cada árvore e, com um fluxo selecionado, o caminho raiz → folha da última medição dele aceso, com o valor de cada coluna ao
lado do limiar, a lista dos passos em texto e a regra da folha. Um seletor alterna entre a árvore oficial (Tarefa 3) e
a ajustada (Tarefa 4); ele muda só o painel: mapa, cartão e placar seguem a oficial. Por isso o `replay` exige também
as saídas do `ajuste` (rode `arvore` e `ajuste` antes) e confere a ajustada refeita contra elas.

As coordenadas das sondas ficam em `src/preditor/visualizacao/sondas.csv`. Para refazê-las (única etapa com rede):
`uv run python -m preditor.visualizacao.coletar_sondas`.

## Como o código está dividido

```text
src/preditor/
  config.py                parâmetros globais: tabela, corte A/B, piso, limiares da regra, horizonte do futuro, recorte, colunas e grade da árvore e caminhos
  spark.py                 SparkSession local (o conector BigQuery só entra no bronze)
  __main__.py              Pipeline         escolhe a camada (ou `arvore`), orquestra, grava e verifica
  bronze/
    ingestao.py            Bronze           tabela do BigQuery → Parquet, como está
  silver/
    medicao.py             Medicoes         Bronze → 1 linha por medição (RTT, jitter, perda, período), sem duplicatas
  gold/
    calculo_x/
      baseline.py          Baseline         ficha por fluxo, só com o Período A
      features.py          Features         métricas relativas e janela das últimas 5 medições
      relatorio_regiao.py  RelatorioRegiao  limites em ms por região (derivado do baseline)
    calculo_y/
      rotulo.py            Rotulo           `regra`, `status_atual` (RFC §8.4) e `status_futuro` (3ª medição à frente)
      recorte.py           Recorte          `bloco`: treino / validação / teste por dois cortes de tempo globais
  modelo/                  fora do medalhão: lê o Gold com pandas, sem Spark
    dados.py               DadosModelo      lê o dataset rotulado, aplica a folga, descarta futuro nulo, separa X e y por bloco
    avaliacao.py           Avaliacao        matriz 3×3, métricas, persistência, erros concretos, transições e regiões
    arvore.py              Arvore           busca na grade, treino, regras em texto; ArvoreContraste
    regras.py              Regras           as 3 regras em português, lidas do caminho real da árvore
    execucao.py            ExecucaoArvore   orquestra, grava em `data/modelo/` e verifica
    ajuste.py              ArvoreAjustada   Tarefa 4: busca com as colunas novas, peso de classe e regra de escolha
    execucao_ajuste.py     ExecucaoAjuste   compara com a Tarefa 3, verifica e grava os arquivos do ajuste
```

As fórmulas seguem a RFC (§8.2 a §8.4). O código comenta cada passo e não
repete a teoria.

## Decisões de implementação

As decisões abaixo foram tomadas sobre o dataset atual e ainda não estão nos documentos da pasta `docs/`:

- **Dataset de 7 dias, e não 14.** A tabela cobre 18/09 a 25/09/2026. O
  Período A são as primeiras **108 h**, o menor corte em que todos os fluxos
  passam de 1.500 RTT válidos. O Período B é o restante, cerca de 2,5 dias.
  As datas de corte citadas na RFC são de uma coleta anterior.
- **RTT válido** = ping com `rtt > 0` e `timeout = false`. No RIPE Atlas, o
  ping com timeout vem com `rtt = 0.0`.
- **RTT da medição** = média dos pings válidos da rajada (equivale ao campo
  `avg` do Atlas). **Jitter** = média de |Δrtt| entre pings consecutivos.
- **`fluxo_id` = `prb_id|dst_addr|msm_id`.** Separa as séries quando mais de
  uma medição do Atlas cobre o mesmo par. Com isso são 81 fluxos no baseline: 79
  com baseline e 2 marcados como `baseline_insuficiente`. Um 82º fluxo só tem
  medições no Período B e também fica fora do modelo (o Silver tem os 82).
- **Região e país são metadados**, não features: a RFC proíbe usá-los na
  árvore.
- **A árvore prevê `status_futuro`** (12 min à frente) e, para não olhar o bloco seguinte, descarta as 3 últimas
  medições de cada fluxo em treino e validação (folga, RFC §9). Valor ausente fica ausente: nada é imputado.
- **Sem balanceamento de classes** nesta primeira árvore: ele fica para o ajuste da Tarefa 4, medido contra ela. A
  árvore é sempre comparada com a persistência, e só a validação escolhe os hiperparâmetros.
