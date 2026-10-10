# Spec: Comparação árvore × Random Forest × XGBoost e exportação do modelo

Status: **aprovada pelo dono em 10/10/2026 e implementada em 10/10/2026** (lotes 1 a 3: M1 a M7). Checkpoint 1 aprovado
(modelos), Checkpoint 2 aprovado (comparação; regra e IC conferidos), lote 3 entregue com o relatório, o exportado e as
checagens. Os critérios de sucesso estão marcados abaixo com a evidência de cada um. Commit: só se o dono pedir.

## Objetivo

Treinar uma Random Forest e um XGBoost nos mesmos dados da árvore, compará-los com a árvore de decisão e com a
persistência na **validação**, escolher o melhor por uma regra fixada **antes** de ver os resultados, exportar o
escolhido num arquivo `.joblib` para a professora usar e escrever o relatório da comparação (por que o modelo escolhido
foi esse). Decisões do dono (10/10/2026): as três famílias competem; o melhor vira o arquivo final; o formato é
`joblib`; o artigo é uma seção de relatório em Markdown.

O RFC deixa a família do algoritmo "para a etapa de modelagem, escolhida na validação" (cabeçalho do RFC). A Tarefa 5
diz "continua sendo uma árvore de decisão" e pede regras em português, mas o dono informou (10/10/2026) que a professora
liberou adaptar o projeto: o roteiro é um modelo a seguir, não uma exigência literal. Logo, **qualquer das três pode
vencer**. A expectativa do dono é que a Random Forest seja a mais efetiva; é uma hipótese, e quem decide é a regra abaixo.

### O que não muda

- Alvo (`status_futuro`), rótulo (com o piso de 30 %), baseline, corte dos blocos, folga, semente 16, `fit` só no treino.
- Os comandos `arvore`, `ajuste` e `replay` e todas as saídas deles: byte a byte iguais. Nada do Gold é recalculado.
- O teste continua fechado. Esta spec **não** mede o teste (a medição única é a Tarefa 5, depois de o dono aprovar o
  modelo). `DadosModelo` continua sem guardar linha do teste e `Avaliacao.medir` continua recusando esse bloco.

## Suposições (corrija agora ou sigo com elas)

1. **Mesmo X para as três famílias: as 10 colunas** da árvore ajustada (`COLUNAS_ARVORE` + `COLUNAS_AJUSTE`). Região,
   país, IP, rota e RTT absoluto continuam proibidos. Valor ausente continua ausente (RF do scikit-learn ≥ 1.4 e o
   XGBoost aceitam `NaN`; nada é imputado).
2. **"A árvore" da comparação é a ajustada com peso** (a adotada na Tarefa 4, `MODELO_AJUSTADA`). A da Tarefa 3 e a
   persistência entram na tabela como referência, mas não como candidatas ao arquivo final.
3. **Peso de classe {OK 1, RISCO 2, FALHA 1,5}** nas três (RF: `class_weight`; XGBoost: `sample_weight` por linha).
   Sem peso, só como linha extra de referência.
4. **Cada família tem sua busca de hiperparâmetros no treino, medida na validação**, como na Tarefa 4. **Sem parada
   antecipada** (`early_stopping`): ela usaria a validação para treinar. O número de árvores faz parte da grade.
5. **O modelo exportado é treinado só no treino** (como todos até aqui), não no treino + validação.
6. **XGBoost no macOS exige a biblioteca OpenMP** (`brew install libomp`); hoje ela não está instalada nesta máquina.
7. Dependências novas: `xgboost` (em `pyproject.toml`). `joblib` já vem com o scikit-learn.

## Comandos

```bash
uv add xgboost                         # dependência nova (Python 3.14 + OpenMP; ver suposição 6)
uv run python -m preditor comparar     # data/gold/ → data/modelo/comparacao/ (treina RF e XGBoost, mede, escolhe)
uv run python -m preditor exportar     # lê a escolha do `comparar`, refaz o modelo, verifica e grava o .joblib
```

Os dois são offline, sem Spark nem Java. `comparar` exige o Gold e as saídas do `ajuste`; `exportar` exige as do
`comparar` (cada um diz qual comando rodar antes). Não entram na execução sem argumento.

## Estrutura

```
src/preditor/modelo/floresta.py          → RandomForest: grade, busca, escolhida (reutiliza ArvoreBase/Avaliacao)
src/preditor/modelo/boosting.py          → XGBoost: idem
src/preditor/modelo/comparacao.py        → regra de escolha, IC pareado por fluxo, tabelas
src/preditor/modelo/execucao_comparacao.py → orquestra, verifica, grava (comparar)
src/preditor/modelo/exportacao.py        → monta e verifica o .joblib (exportar)
src/preditor/config.py                   → grades, tolerância, nomes de arquivo, semente (com origem de cada número)
docs/relatorio_comparacao_modelos.md     → o relatório (feito por último, só com números de execução)
```

Saídas em `data/modelo/comparacao/` (ignorada pelo git): `busca_floresta.csv`, `busca_boosting.csv`,
`comparacao_modelos.csv` (métricas das 5 linhas: persistência, Tarefa 3, ajustada, RF, XGBoost), `matriz_comparacao.csv`,
`ic_pareado.csv`, `escolha.json` (modelo, parâmetros, motivo), `importancias.csv`. Exportação em
`data/modelo/exportado/`: `modelo_final.joblib`, `arvore_ajustada.joblib`, `LEIA-ME.md` e `exemplo_de_uso.py`.

## Regra de escolha (fixada antes dos resultados)

1. Dentro de cada família, a escolha usa a regra da Tarefa 4: entre as combinações a até **0,005** do melhor F1 macro
   da validação, vence a mais simples (menos árvores, depois menor profundidade, depois folha mínima maior).
2. Entre as famílias vale a mesma regra: a até **0,005** do melhor F1 macro da validação, vence a mais simples
   (árvore, depois Random Forest, depois XGBoost). Assim, floresta ou boosting só ganham se passarem a árvore por mais
   que a tolerância. O IC 95 % (bootstrap por fluxo, 2.000 reamostras, semente 16, mesma reamostragem nas duas) da
   diferença pareada contra a árvore é **gravado e dito no relatório**, mas não decide: o relatório diz se o ganho
   tem prova de ser maior que o ruído.
3. Todo candidato precisa superar a persistência no mesmo conjunto de linhas; senão, o resultado é declarado assim
   (a Tarefa 5 já prevê o caso "detector").
4. Reportar também: recall de FALHA, F1 por classe, OK → FALHA, tamanho do modelo (nós/árvores), tempo de treino e de
   previsão. A regra não escolhe por eles, mas o relatório os diz.

## Verificações automáticas (como nas outras camadas)

- X com exatamente as 10 colunas e nenhuma proibida; nenhuma linha do teste lida ou medida; 3 classes em treino e validação.
- `fit` só com o treino; matrizes somam o N da validação; F1 macro = média dos 3 F1; as linhas comparadas são as
  mesmas para todos os modelos (mesmo índice).
- A árvore ajustada refeita aqui = `arvore_ajustada.json` e `metricas_ajuste.csv`; persistência e Tarefa 3 = os CSVs de hoje.
- A escolhida de cada família é a determinada pela regra a partir do CSV de busca (conferida de novo).
- Mesma semente = mesmas previsões (rodar duas vezes). Os arquivos de `arvore`, `ajuste` e `replay` não mudam.
- Exportação: o `.joblib` recarregado, num processo novo, dá **exatamente** as previsões do modelo em memória nas
  linhas da validação; aceita `NaN`; devolve só `OK`/`RISCO`/`FALHA`; o conteúdo só usa classes do scikit-learn, do
  XGBoost e da biblioteca padrão (não pode exigir o pacote `preditor` para abrir); os metadados trazem as 10 colunas na
  ordem, as classes, a semente e as versões das bibliotecas.

## Relatório (`docs/relatorio_comparacao_modelos.md`)

Tabela das 5 linhas na validação, IC pareado, onde cada família erra (OK → FALHA, FALHA isolada), importância das
colunas, custo (tamanho, tempo), interpretabilidade (regras em português só a árvore tem), o teto dos dados (seção 7
do relatório de análise) e a decisão com a regra acima. Cada número vem de uma execução; ressalvas ditas (validação
usada tanto para escolher quanto para comparar, N de fluxos, F1 incomparável com o rótulo anterior). Estilo e
cuidados do `relatorio_analise_arvore.md`. Linkado em `docs/README.md`.

## Testes

Não há framework de testes no projeto: a verificação é rodar os comandos e as checagens acima, que param com
mensagem clara. Os dois comandos novos terminam com "todas as checagens passaram" ou com o motivo da falha.

## Limites

- **Sempre:** português no código e nos docs; todo número em `config.py` com origem; nada de linha do teste;
  nenhuma checagem afrouxada; nada commitado sem o dono pedir.
- **Perguntar antes:** instalar o `libomp` (Homebrew); trocar o modelo exportado por outro que não saiu da regra;
  mexer em `arvore`, `ajuste`, `replay` ou no Gold; medir o teste.
- **Nunca:** escolher hiperparâmetro ou modelo olhando o teste; imputar `NaN`; usar região, país, IP ou RTT absoluto;
  exportar sem a verificação de recarga; versionar o `.joblib` ou os CSVs (ficam em `data/`, ignorada).

## Riscos

1. **Legibilidade.** Se RF ou XGBoost vencerem, o modelo final não tem regras em português (a professora liberou
   adaptar, mas o relatório diz o custo). Mitigação: exportar também a árvore ajustada, que continua legível.
2. **Teto dos dados.** O relatório (seção 7) mediu que nem um boosting de 300 árvores com 20 colunas passou de ~0,77 de
   F1 macro com o rótulo anterior. É provável que o ganho seja pequeno ou nulo; o relatório diz o que sair, sem forçar.
3. **`.joblib`/pickle executa código ao abrir.** O `LEIA-ME.md` avisa que só se abre arquivo de fonte confiável, e traz
   o hash SHA-256. Versões diferentes de scikit-learn/XGBoost podem não abrir: as versões vão no `LEIA-ME.md` e nos metadados.
4. **Validação reaproveitada** para escolher hiperparâmetro e comparar famílias: a escolha entre famílias fica levemente
   otimista. O IC pareado e a exigência de excluir o zero limitam isso, e o relatório diz.

## Critérios de sucesso

1. [x] `comparar` termina com todas as checagens; as 5 linhas medidas nas mesmas linhas da validação; teste intocado.
   *Evidência:* três execuções com "todas as checagens passaram" (10/10/2026); N da validação = 13.490 nas cinco linhas;
   `Avaliacao` recusa o teste (verificado em `execucao_comparacao.py`).
2. [x] `arvore`, `ajuste` e `replay` produzem saídas idênticas às de hoje.
   *Evidência:* `diff -rq -x comparacao data/modelo data/modelo_antes_comparacao` vazio e `cmp` do `replay.json` igual,
   depois do último código (`data/modelo_antes_comparacao/` e `data/replay_antes_comparacao.json`).
3. [x] A escolha segue a regra e é reproduzível (mesma semente, mesma escolha), com o IC pareado gravado.
   *Evidência:* a escolha é a Random Forest (regra refeita a partir de `comparacao_modelos.csv` e de `busca_*.csv`); duas
   execuções idênticas; `ic_pareado.csv` gravado com 2.000 reamostras.
4. [x] `exportar` grava `modelo_final.joblib` que, recarregado em processo novo, reproduz as previsões; o `LEIA-ME.md` e o
   `exemplo_de_uso.py` funcionam numa máquina só com scikit-learn/XGBoost.
   *Evidência:* reabertura em processo novo reproduz as 13.490 previsões da validação; F1 recalculado = 0,697713828;
   SHA-256 no LEIA-ME. *Desvio:* o `exemplo_de_uso.py` e o LEIA-ME pedem também **pandas** (a entrada é uma tabela); o
   `.joblib` em si não precisa de pandas nem do pacote `preditor`.
5. [x] `docs/relatorio_comparacao_modelos.md` existe, com todo número vindo de execução e com a justificativa da escolha.
   *Evidência:* o relatório traz as tabelas dos CSVs, os IC, a regra e as ressalvas; as figuras são linkadas de
   `docs/figuras_artigo/`; a versão narrativa continua em `docs/guia_para_o_artigo.md` (com três correções registradas).
6. [x] `AGENTS.md` e `docs/README.md` atualizados (comandos, decisões, estágio).
   *Evidência:* seções "Project", "Stack", "Commands", "Conventions", "Decisions" e "Agent workflow" do `AGENTS.md`;
   entrada do relatório no `docs/README.md`.

## Perguntas em aberto

1. Posso instalar o `libomp` com Homebrew para o XGBoost funcionar? *Resolvida: sim (10/10/2026); instalado (libomp 23.1.3).*
2. ~~A professora aceita um modelo final que não seja árvore?~~ Resolvida em 10/10/2026: sim, o roteiro é adaptável.
3. A medição única no teste (Tarefa 5) entra neste trabalho ou fica para um passo seguinte? Suposição: fica depois. *Resolvida: fica depois; o teste continua fechado.*
4. A comparação inclui a árvore da Tarefa 3 como candidata ao arquivo final, ou só a ajustada? Suposição: só a ajustada. *Resolvida: só a ajustada (a Tarefa 3 é só referência na tabela).*
