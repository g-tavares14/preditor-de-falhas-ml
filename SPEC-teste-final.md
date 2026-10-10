# Spec: Teste único da Tarefa 5 (modelo final)

Status: **executado** (10/10/2026). Aprovada pelo dono; o teste foi aberto **uma vez** em 10/10/2026, às 14:49
(`data/modelo/teste/TESTE_ABERTO.json`, `concluido`). Resultado em `docs/resultado_teste_final.md`; ficha em
`docs/ficha_modelo_final.md`.

## Objetivo

Medir **uma única vez** o modelo escolhido na comparação (Random Forest, `data/modelo/exportado/modelo_final.joblib`) no
bloco de **teste**, guardado fechado desde a Tarefa 2, e entregar o que o diário da Tarefa 5 pede
(`docs/projeto_preditor_redes/tarefas/Tarefa5_Arvore_Final.md`): matriz 3×3 em contagem, precisão, recall e F1 por
classe, F1 macro, recall de FALHA e a troca RISCO ↔ FALHA, dois casos concretos (fluxo e horário), a comparação com a
persistência, a checagem de fluxo não visto (ou a limitação declarada) e a ficha do modelo.

O RFC pede, para o preditor de 12 minutos, superar a persistência no mesmo teste; senão, a entrega se declara
**detector** (RFC, critério 3). A professora liberou adaptar o roteiro (10/10/2026): o modelo medido é a Random Forest,
não a "árvore" do diário.

### O que não muda

- Alvo, rótulo (piso de 30 %), baseline, blocos, folga, semente 16. O modelo e os hiperparâmetros já estão escolhidos
  pela validação (`comparar`) e **não são tocados**: nada é retreinado nem reajustado depois de abrir o teste.
- `arvore`, `ajuste`, `replay`, `comparar` e `exportar` e as saídas deles: byte a byte iguais.
- `DadosModelo` continua sem guardar linha do teste. O teste é lido por um módulo novo, que só o comando `teste` usa.

## Regras fixadas antes de abrir o teste

1. **Quem é medido:** a Random Forest do `.joblib` exportado (o arquivo, não um modelo refeito) e a persistência, nas
   **mesmas linhas**. O SHA-256 do `.joblib` e o do `escolha.json` são gravados no resultado; se o arquivo mudou desde a
   exportação, o comando para.
2. **Quais linhas:** blocos `teste` do `dataset_rotulado_B.parquet` com `status_futuro` não nulo. Não há folga a aplicar
   no teste (o futuro nulo das últimas medições é fim de série). O N tem de ser igual ao `n_teste` que o `DadosModelo` já
   conta. O X são as 10 colunas do modelo, com `NaN` como `NaN`.
3. **Métricas:** matriz 3×3 em contagem; precisão, recall e F1 de OK, RISCO e FALHA; F1 macro; acurácia balanceada;
   acerto por transição (agora → futuro, em especial OK → FALHA e FALHA → OK) e quando o futuro muda; as mesmas da
   validação, calculadas pelas mesmas funções (`Avaliacao`).
4. **Preditor ou detector (regra de declaração):** o IC 95 % por fluxo (bootstrap, 2.000 reamostras, semente 16, a mesma
   reamostragem nas duas séries) do ganho de F1 macro sobre a persistência. Se o IC **excluir o zero**, a entrega é
   declarada **preditor de 12 minutos**; senão, **detector do estado atual**. O recall de FALHA e a precisão de FALHA
   são ditos de qualquer jeito.
   *Leitura registrada (decisão do dono, 10/10/2026):* "excluir o zero" quer dizer **limite inferior maior que zero**.
   Um IC todo abaixo de zero, ou que cruza o zero, não declara preditor. O texto da regra acima não muda.
5. **Dois casos concretos**, com o mesmo critério dos "erros concretos" da validação (`CASOS_ERRO`, `Avaliacao._escolher`:
   sem sorteio, ordem total por `rtt`, `fluxo_id`, `t`): um **acerto em caminho longo estável** (verdadeiro OK, previsto
   OK) e um **erro relevante** (FALHA real prevista como OK). A saída diz o `fluxo_id` e o horário de cada um.
6. **Ao lado da validação:** a saída mostra os números da validação (de `data/modelo/comparacao/`) junto aos do teste,
   para o leitor ver a diferença. Não se escolhe nem se ajusta nada com ela.
7. **Resultado é resultado:** se o teste sair pior que a validação, ou a persistência ganhar, grava-se assim. Nada de
   trocar modelo, hiperparâmetro, rótulo ou alvo depois (diário da Tarefa 5, itens 1 e 2).

## Travas contra abrir o teste duas vezes

- O comando exige o argumento `--abrir-o-teste` (sem ele, só explica o que faria e sai). Isso evita rodar por engano.
- Ao começar, grava `data/modelo/teste/TESTE_ABERTO.json` (data e hora, SHA-256 do modelo, N, estado `em_andamento`); no fim,
  muda para `concluido`. Se o arquivo existe, o comando **recusa** (nos dois estados). Apagá-lo é decisão do dono e deve
  ser registrada no relatório; o código não o apaga.
- **Ensaio na validação:** `teste --ensaio` roda o **mesmo caminho de código** nas linhas da **validação** (nunca toca o
  teste) e confere que os números saem iguais aos de `comparacao_modelos.csv` (F1 macro 0,6977, matriz da floresta,
  recall de FALHA 0,505). É o que prova que o código está certo antes de gastar o teste. O ensaio tem de passar antes de
  a abertura ser aceita (o comando checa o carimbo do ensaio, gravado em `data/modelo/teste/ensaio_ok.json`).
- O código que lê o bloco de teste (`modelo/dados_teste.py`) só pode ser importado por `execucao_teste.py`: uma checagem
  (`grep` do projeto) confere que nenhum outro módulo o importa.
- `Avaliacao.medir` continua recusando o teste por padrão; ganha um parâmetro explícito para liberá-lo, e os outros
  comandos não o passam (suas saídas não mudam).

## Fluxo que o modelo não viu (achado, verificado só com contagens de fluxo)

Os 79 fluxos com baseline aparecem nos três blocos (treino, validação e teste). Dos 81 do baseline, 2 têm baseline
insuficiente e nem entram no dataset rotulado; o 82º `fluxo_id` do Silver só tem medições depois do Período A e não tem
ficha. Logo **não há fluxo fora do treino com baseline suficiente**, e o diário manda escrever isso, sem forçar a conta
(seção 3 do diário: "Se não houver fluxo sobrando com baseline suficiente, escrever isso e não forçar a conta"). A saída
do `teste` imprime essa contagem, conferida por código, e o relatório declara a limitação.

*Opcional, desligado por padrão (ver Perguntas):* uma verificação por fluxo na **validação** (treinar sem alguns
fluxos e medir neles), claramente rotulada como exploratória e sem tocar o teste.

## Saídas

Em `data/modelo/teste/` (ignorada pelo git): `matriz_teste.csv`, `metricas_teste.csv`, `ic_ganho_teste.csv`,
`casos_teste.txt`, `resultado.json` (modelo, SHA-256, N, data, declaração preditor/detector), `ensaio_ok.json` e
`TESTE_ABERTO.json`. Em `docs/` (versionados, só com números de execução): `resultado_teste_final.md` (o relatório da
Tarefa 5, no estilo dos outros) e `ficha_modelo_final.md` (a ficha da seção 5 do diário: problema, unidade, baseline,
colunas, modelo e parâmetros, F1 macro e recall de FALHA no teste, o que não faz, como reproduzir).

## Comandos

```bash
uv run python -m preditor teste --ensaio          # mesmo código, nas linhas da VALIDAÇÃO; precisa passar antes
uv run python -m preditor teste --abrir-o-teste   # abre o teste UMA vez (recusa se TESTE_ABERTO.json existir)
```

Offline, sem Spark nem Java; exige o Gold, o `modelo_final.joblib` e as saídas do `comparar`. Não entram na execução
sem argumento.

## Estrutura

```
src/preditor/modelo/dados_teste.py       → lê só o bloco de teste (X de 10 colunas, y, status_atual, localização)
src/preditor/modelo/execucao_teste.py    → orquestra: trava, ensaio, medição, IC, casos, verificação, gravação
src/preditor/modelo/avaliacao.py         → ganha o parâmetro que libera o teste (padrão: recusa)
src/preditor/config.py                   → nomes de arquivo e constantes (com origem)
src/preditor/__main__.py                 → comando `teste` e os dois argumentos
docs/resultado_teste_final.md            → relatório da Tarefa 5 (depois de rodar)
docs/ficha_modelo_final.md               → a ficha (depois de rodar)
```

## Verificações automáticas

- Ensaio: os números na validação são iguais aos de `comparacao_modelos.csv` (F1 macro, recalls, matriz) e o X tem as
  10 colunas, na ordem do `.joblib`.
- Teste: N = `n_teste`; X com as 10 colunas e nenhuma proibida; as 3 classes em `verdadeiro`; matriz soma o N e o F1
  macro é a média dos 3 F1; a persistência e o modelo estão nas mesmas linhas; modelo = o do SHA-256 gravado; o IC é
  reproduzível (mesma semente, mesmo resultado); os casos escolhidos conferidos por outro caminho (como em
  `_verificar_erro`); nenhum arquivo de `data/modelo/` fora de `teste/` mudou; nenhum outro módulo importa `dados_teste`.
- `arvore`, `ajuste`, `replay`, `comparar` e `exportar` seguem com saídas idênticas (diff contra cópias de referência).
- Nada retreinado: o comando não chama `fit`.

## Limites

- **Sempre:** português; todo número em `config.py` com origem; resultados só em `data/` e relatórios em `docs/`;
  nada commitado sem o dono pedir.
- **Perguntar antes:** apagar `TESTE_ABERTO.json`; rodar o teste uma segunda vez; medir outro modelo no teste; mudar
  qualquer coisa do `modelo_final.joblib` depois do ensaio.
- **Nunca:** olhar o teste antes de o ensaio passar; escolher ou ajustar modelo, hiperparâmetro, rótulo, alvo ou regra de
  declaração depois de ver o teste; reaproveitar linhas do teste em treino ou validação; imprimir o teste fora da
  execução de abertura.

## Riscos

1. **A trava é do código, não do dono.** Quem apaga o `TESTE_ABERTO.json` reabre o teste. Mitigação: o relatório
   registra a data e o SHA-256 da abertura; se o arquivo for apagado, isso deve constar.
2. **Falha no meio da abertura.** O teste pode ter sido visto sem os arquivos gravados. Por isso o estado
   `em_andamento` também bloqueia: o dono decide o que fazer, registrando.
3. **Resultado pior (ou melhor) que o da validação.** A validação tem 79 fluxos e FALHA rara (4,4 % do alvo); o teste é
   outro trecho do tempo e pode ter uma proporção diferente. O F1 pode cair ou subir; o relatório declara sem retrabalho.
4. **Distribuição diferente no teste.** O teste é o trecho mais recente (24/09 08:09 a 25/09 02:07), e o piso muda a
   proporção das classes. O relatório mostra as proporções do teste (só contagens) ao lado das da validação.
5. **Dicionário v0.4:** o diário o cita; não está neste repositório (ver Perguntas).

## Critérios de sucesso

Evidência de cada critério (10/10/2026). Os números vêm das execuções, não de digitação.

1. [x] O ensaio passa e reproduz os números da floresta na validação. *Evidência:* `teste --ensaio` com exit 0 e o
   carimbo `data/modelo/teste/ensaio_ok.json` (F1 macro 0,6977; recall de FALHA 0,5051; matriz e IC iguais aos de
   `comparacao_modelos.csv`, `matriz_comparacao.csv` e `ic_pareado.csv`). Rodado de novo depois da última mudança de código.
2. [x] `teste --abrir-o-teste` roda uma vez, com todas as checagens; a segunda tentativa é recusada. *Evidência:*
   `TESTE_ABERTO.json` em `concluido`, aberto às 14:49:21 e concluído às 14:49:23 (a conclusão só acontece depois de todas
   as checagens e da releitura do disco). A sessão principal relatou que a segunda tentativa foi recusada (eu não a repeti). As
   recusas da abertura foram testadas em pasta temporária (`verifica_t4.py`, 12 casos).
3. [x] Saem a matriz 3×3 em contagem, precisão/recall/F1 por classe, F1 macro, recall de FALHA, IC do ganho sobre a
   persistência e a declaração preditor/detector pela regra acima. *Evidência:* `matriz_teste.csv`,
   `metricas_teste.csv`, `ic_ganho_teste.csv` e `resultado.json`; em `docs/resultado_teste_final.md` (seções 3 a 7).
4. [x] Os dois casos saem com `fluxo_id` e horário, escolhidos sem sorteio e conferidos. *Evidência:* `casos_teste.txt`
   (acerto 6349|202.6.102.41|154581679, 2026-09-24 20:27:49; erro 6891|150.164.1.222|28095697, 2026-09-24 15:08:00). A
   escolha é por `Avaliacao._escolher` e conferida por laço (`Avaliacao._verificar_erro`).
5. [x] A limitação do fluxo novo está declarada, com a contagem conferida. *Evidência:* `resultado.json` (`fluxos`:
   79 com baseline nos três blocos, 0 fora do treino, 2 insuficientes fora do dataset) e a seção 9 do relatório. O teste
   não mede fluxo novo, e isso está dito.
6. [x] `docs/resultado_teste_final.md` e `docs/ficha_modelo_final.md` existem, com todo número vindo de execução.
   *Evidência:* os dois arquivos, com a tabela de fontes (seção 10 do relatório).
7. [x] `arvore`, `ajuste`, `replay`, `comparar` e `exportar` seguem idênticos; `AGENTS.md` e `docs/README.md` atualizados.
   *Evidência:* a identidade foi conferida depois da T4 (`t4_log.txt`: exit 0 nos cinco; `cmp` do `replay.json` igual;
   `diff -rq -x teste` só em `tempos.csv`, na coluna `segundos`; SHA do `.joblib` igual). Depois da abertura, nenhum
   arquivo de `src/`, `web/dados/` ou `data/modelo/` mudou. `AGENTS.md` e `docs/README.md` foram atualizados em 10/10/2026.

## Perguntas em aberto

1. **Só a Random Forest e a persistência no teste?** Suposição: sim. Medir também a árvore ajustada e o XGBoost gasta o
   "uma vez" em mais modelos; o ganho seria mostrar a árvore legível no teste. Se quiser a árvore, ela entra só como
   referência declarada, não como candidata.
2. **Verificação exploratória de fluxo não visto na validação?** Suposição: desligada. Daria uma resposta parcial à
   seção 3 do diário, mas é um modelo diferente do exportado (treinado sem alguns fluxos).
3. **Dicionário v0.4:** onde está? O diário o pede igual às colunas usadas, e não o encontrei no repositório. Se a
   professora forneceu, preciso do arquivo; senão, a ficha traz o dicionário das 10 colunas e a gente marca que é o
   nosso.
4. **Quando abrir?** O diário da Tarefa 5 vai de 12/10 a 25/10/2026. O teste só deve ser aberto quando o dono confirmar
   que o modelo, a ficha e as regras de declaração estão como quer.

**Respostas registradas em 10/10/2026:**

- (1) Sim: só a Random Forest e a persistência foram medidas no teste. A árvore ajustada e o XGBoost não entraram.
- (2) Desligada: a verificação exploratória de fluxo não visto na validação não foi feita.
- (3) **Pendente do dono.** O dicionário v0.4 não está no repositório. A ficha traz as 10 colunas com o dicionário do grupo,
  marcado como tal, e pede a conferência.
- (4) Aberto em 10/10/2026, às 14:49, depois do Checkpoint 2 e da autorização do dono.
