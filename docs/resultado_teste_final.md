# Relatório: teste único da Tarefa 5 (Random Forest × persistência)

Data: 10/10/2026. Abertura do teste: 14:49:21, conclusão: 14:49:23 (horário de Brasília). Spec: `SPEC-teste-final.md`
(aprovada pelo dono em 10/10/2026). Plano e tarefas: `tasks/plan-teste-final.md` e `tasks/todo-teste-final.md`. A
ficha do modelo, com as colunas e como reproduzir, está em [`ficha_modelo_final.md`](ficha_modelo_final.md).

**Como foi feito.** O teste foi aberto **uma vez**, pelo comando `uv run python -m preditor teste --abrir-o-teste`, com
o carimbo do ensaio válido e a trava `TESTE_ABERTO.json` gravada antes da leitura. Todos os números deste relatório
vêm de `data/modelo/teste/` (gravados pela abertura) ou de `data/modelo/comparacao/` (validação, para comparar). Nada
foi retreinado, reajustado ou re-escolhido depois. A tabela de fontes da seção 10 diz de onde sai cada número.

> **Teste aberto.** Desde 10/10/2026 o conjunto de teste não está mais fechado. Os resultados abaixo são o resultado
> do teste único. Os relatórios de validação continuam válidos para a validação, e não foram reescritos.

## 1. Resumo

- **Medido no teste:** a Random Forest exportada (`modelo_final.joblib`) e a persistência ("daqui a 12 minutos, igual a
  agora"), nas mesmas **20.507 medições** do bloco de teste, nos mesmos 79 fluxos. A árvore ajustada e o XGBoost não
  foram medidos no teste (a spec mede só o modelo escolhido e a persistência).
- **F1 macro:** Random Forest **0,6699** (validação 0,6977); persistência 0,6132 (validação 0,6355). **A queda foi real:**
  o modelo caiu 0,0278 da validação para o teste.
- **Ganho sobre a persistência no teste:** +0,0567, com IC 95 % por fluxo de **[+0,0168; +0,0658]**. Na validação era
  +0,0622 [+0,0268; +0,0750]. O ganho segue positivo, mas o limite inferior ficou perto de zero.
- **Declaração pela regra da spec:** **preditor de 12 minutos**, porque o limite inferior do IC (+0,0168) é maior que
  zero. A regra 4 da spec foi lida pelo dono como "limite inferior maior que zero"; IC abaixo de zero ou cruzando o zero
  não declararia preditor. A prova é **fraca**: o intervalo mal sai do zero.
- **O recall de FALHA ficou abaixo da persistência:** a Random Forest acha **38,2 %** das falhas do teste (persistência
  43,1 %). Na validação ela achava 50,5 %. A precisão de FALHA da floresta, no entanto, é **70,3 %** (persistência
  43,4 %), e o F1 de FALHA da floresta (0,495) continua acima do da persistência (0,432). Ou seja: ela acha menos
  falhas, mas acerta mais quando aponta uma.
- **OK → FALHA:** quando o caminho está OK e vai virar FALHA em 12 minutos, a floresta acerta **12,2 %** das vezes (409
  casos). Na validação eram 17,4 %. Antecipar o começo de uma falha segue sendo o ponto fraco.
- **Escolha do modelo:** a Random Forest foi escolhida pela regra do empate (tolerância de 0,005 sobre o maior F1
  macro da validação, e depois o mais simples). O XGBoost tinha F1 macro maior na validação (0,7006 contra 0,6977), e
  não foi medido no teste. O resultado do teste é o da Random Forest, não o do melhor número da validação.
- **Rótulo é política:** o alvo é a classe pela regra da RFC com o piso de 30 % de aumento na linha 3. O modelo aprende
  essa definição de falha em medições de ping, não uma falha real de equipamento.

## 2. O que foi medido e em quais medições

| Bloco | Período (intervalo das linhas) | Medições com alvo (N) | Usado para |
|---|---|---|---|
| Treino | 22/09 14:10 a 23/09 20:08 | 34.661 | treinar (só o `fit`) |
| Validação | 23/09 20:09 a 24/09 08:08 | 13.490 | escolher e comparar as famílias |
| **Teste** | **24/09 08:09 a 25/09 02:07** | **20.507** | **medição única** (este relatório) |

- O N é o das linhas com `status_futuro` (a classe 3 medições à frente). No teste não há folga: as linhas sem futuro
  são só o fim da série. O bloco de teste tem 21.148 linhas antes de descartar o futuro nulo (`contagem_classes.csv`).
- O conjunto de entrada (X) são as **10 colunas** do modelo (`modelo_final.joblib`, lista `colunas`), com valores
  ausentes mantidos como ausentes. Nenhuma coluna de região, país, IP, rota ou RTT absoluto entrou no X.
- A persistência usa `status_atual` como previsão: ela não é um modelo treinado, só a régua.

## 3. Matriz 3×3 em contagem (teste)

Random Forest. Linha = classe verdadeira (`status_futuro`), coluna = classe prevista.

| Verdadeiro \ previsto | OK | RISCO | FALHA | Total |
|---|---|---|---|---|
| **OK** | 14.631 | 944 | 143 | 15.718 |
| **RISCO** | 1.371 | 2.109 | 59 | 3.539 |
| **FALHA** | 375 | 398 | 477 | 1.250 |
| Total previsto | 16.377 | 3.451 | 679 | 20.507 |

Persistência, mesmas linhas:

| Verdadeiro \ previsto | OK | RISCO | FALHA | Total |
|---|---|---|---|---|
| **OK** | 13.921 | 1.404 | 393 | 15.718 |
| **RISCO** | 1.379 | 1.849 | 311 | 3.539 |
| **FALHA** | 409 | 302 | 539 | 1.250 |

## 4. Precisão, recall e F1 por classe

Teste (`metricas_teste.csv`, persistência e floresta; precisão calculada da matriz pela mesma conta de
`Avaliacao.medir`). Validação: F1 e recall de `comparacao_modelos.csv`; precisão calculada da matriz de
`matriz_comparacao.csv`.

| Modelo | Classe | Precisão | Recall | F1 | Validação: F1 | Validação: recall |
|---|---|---|---|---|---|---|
| Random Forest | OK | 0,8934 | 0,9308 | 0,9117 | 0,9173 | 0,9360 |
| Random Forest | RISCO | 0,6111 | 0,5959 | 0,6034 | 0,5773 | 0,5425 |
| Random Forest | **FALHA** | 0,7025 | **0,3816** | 0,4946 | 0,5986 | 0,5051 |
| Persistência | OK | 0,8862 | 0,8857 | 0,8859 | 0,8943 | 0,8944 |
| Persistência | RISCO | 0,5201 | 0,5225 | 0,5213 | 0,5119 | 0,5120 |
| Persistência | **FALHA** | 0,4336 | **0,4312** | 0,4324 | 0,5004 | 0,4983 |

- **F1 macro:** Random Forest 0,6699 (validação 0,6977); persistência 0,6132 (validação 0,6355). A média é simples: cada
  classe pesa igual, mesmo a FALHA, que é a rara.
- **Balanced accuracy** (média dos recalls): Random Forest 0,6361; persistência 0,6131.
- **Acurácia** (só informativa, porque OK é a maioria): Random Forest 0,8396 (validação 0,8551); persistência 0,7953
  (validação 0,8168).

## 5. Recall de FALHA e a troca RISCO ↔ FALHA

**Recall de FALHA.** A floresta acha 477 das 1.250 falhas do teste (38,2 %). A persistência acha 539 (43,1 %). Na
validação a floresta achava 50,5 %, então a queda no teste é grande (12 pontos). A persistência também caiu no teste
(de 49,8 % para 43,1 %), o que mostra que o trecho do teste é mais difícil para qualquer régua, não só para o modelo.
Mesmo assim, a floresta ficou abaixo da régua no recall de FALHA. Esse é o ponto fraco do modelo neste teste.

**A troca RISCO ↔ FALHA.** Das 773 falhas que a floresta perdeu, **398 foram para RISCO** e **375 foram para OK**. Ou
seja, metade dos erros em FALHA é o modelo achar que a falha virou um aviso, e a outra metade é achar que o caminho
voltou ao normal. No sentido contrário, dos 3.539 RISCO reais, só **59** foram para FALHA (1,7 %). O modelo quase nunca levanta alarme
de FALHA em cima de um RISCO.

A persistência faz a mesma troca de outro jeito: 302 falhas viraram RISCO, e 311 RISCOs viraram FALHA (o caso em que o
estado atual RISCO já se agravou sozinho). A floresta, por sua vez, troca menos RISCO por FALHA (59 contra 311).

**Precisão de FALHA.** Quando a floresta aponta FALHA, acerta 477 de 679 vezes (70,3 %). A persistência acerta 539 de
1.243 (43,4 %). A floresta é mais conservadora: aponta menos falhas, e a maioria das que aponta é de fato falha. O F1 de
FALHA da floresta (0,495) ainda supera o da persistência (0,432), porque a precisão compensa o recall. Mas o F1 da
validação era 0,599, e a queda foi de 0,104 em FALHA, a maior queda entre as três classes.

## 6. Acerto por transição (agora → futuro)

Mesma leitura do relatório de comparação: a transição é o estado agora (`status_atual`) e o futuro verdadeiro. Os
números do teste vêm de `metricas_teste.csv`; os da validação, de `comparacao_modelos.csv` (só os pares que o arquivo
grava).

| Transição | Medições (teste) | Acerto da floresta (teste) | Acerto da floresta (validação) |
|---|---|---|---|
| OK → OK | 13.921 | 98,1 % | — |
| OK → RISCO | 1.379 | 19,3 % | — |
| **OK → FALHA** | **409** | **12,2 %** | 17,4 % (201 casos) |
| RISCO → OK | 1.404 | 54,2 % | — |
| RISCO → RISCO | 1.849 | 87,3 % | — |
| RISCO → FALHA | 302 | 2,6 % | — |
| **FALHA → OK** | **393** | **55,0 %** | 59,8 % (194 casos) |
| FALHA → RISCO | 311 | 73,6 % | — |
| FALHA → FALHA | 539 | 77,7 % | — |

- **Futuro igual ao agora** (o modelo acerta quando nada muda): 16.309 medições, acerto 96,2 % (validação 96,7 %).
- **Futuro muda** (é onde prever vale alguma coisa): 4.198 medições, acerto 36,4 % (validação 35,7 %).
- A persistência acerta 100 % do primeiro grupo e 0 % do segundo, porque por definição ela nunca muda. A floresta não é
  uma régua de "nada muda": ela acerta bem o grupo que não muda e acerta pouco o que muda.

## 7. Dois casos concretos (fluxo e horário)

Escolhidos pelo critério da validação, sem sorteio: ordem por `rtt` (maior no caso 1, menor no caso 2), depois
`fluxo_id` e `t`. A conferência foi feita por outro caminho (laço), dentro do próprio comando. Texto integral em
`data/modelo/teste/casos_teste.txt`.

**Caso 1: acerto em caminho longo e estável.** `fluxo_id` **6349|202.6.102.41|154581679**, horário **2026-09-24
20:27:49**, rtt 382,28 ms. Mediana do fluxo acima da mediana das medianas (209,73 ms), `|z_robusto| ≤ 1`. Verdadeiro OK,
previsto OK, `status_atual` OK. Havia 1.813 medições atendendo ao critério; esta é a primeira da lista ordenada.

**Caso 2: erro relevante, FALHA prevista como OK.** `fluxo_id` **6891|150.164.1.222|28095697**, horário **2026-09-24
15:08:00**, rtt 0,14 ms. Mediana do fluxo abaixo da mediana das medianas, caminho curto. Verdadeiro FALHA, previsto OK,
`status_atual` **FALHA**. Havia 256 medições atendendo ao critério.

Duas leituras honestas desses casos:

- No caso 2 a falha **já estava em curso** (`status_atual` FALHA). A persistência acertaria este caso (previsto FALHA).
  A floresta errou ao dizer OK doze minutos depois. É o tipo de erro que a troca RISCO ↔ FALHA da seção 5 descreve.
- O rtt de 0,14 ms é muito baixo para um destino fora da rede local. O fluxo é o mesmo que aparece no ensaio da
  validação (0,12 ms). Antes de citar este caso no artigo, vale o dono confirmar se o destino 150.164.1.222 é de fato uma
  máquina da mesma rede da sonda 6891. Não mudei nada por causa disso.

## 8. Comparação com a validação

| Número | Validação (Random Forest) | Teste (Random Forest) | Variação | Validação (persistência) | Teste (persistência) |
|---|---|---|---|---|---|
| F1 macro | 0,6977 | **0,6699** | −0,0278 | 0,6355 | 0,6132 |
| F1 OK | 0,9173 | 0,9117 | −0,0055 | 0,8943 | 0,8859 |
| F1 RISCO | 0,5773 | 0,6034 | +0,0261 | 0,5119 | 0,5213 |
| F1 FALHA | 0,5986 | **0,4946** | −0,1040 | 0,5004 | 0,4324 |
| Recall FALHA | 0,5051 | **0,3816** | −0,1235 | 0,4983 | 0,4312 |
| Precisão FALHA | 0,7346 | 0,7025 | −0,0321 | 0,5026 | 0,4336 |
| OK → FALHA (acerto) | 17,4 % | 12,2 % | −5,2 pontos | 0,0 % | 0,0 % |
| Ganho de F1 macro sobre a persistência | +0,0622 | **+0,0567** | −0,0055 | — | — |
| IC 95 % do ganho | [+0,0268; +0,0750] | [+0,0168; +0,0658] | — | — | — |

Fontes: validação de `comparacao_modelos.csv`, `matriz_comparacao.csv` (precisão calculada da matriz) e `ic_pareado.csv`;
teste de `metricas_teste.csv`, `matriz_teste.csv`, `ic_ganho_teste.csv` e `resultado.json`.

**Proporção de classes** (só contagens, do `resultado.json`):

| Classe | Validação (13.490) | Teste (20.507) |
|---|---|---|
| OK | 10.771 (79,8 %) | 15.718 (76,6 %) |
| RISCO | 2.127 (15,8 %) | 3.539 (17,3 %) |
| FALHA | 592 (4,4 %) | 1.250 (6,1 %) |

O teste tem **mais falhas em proporção** (6,1 % contra 4,4 %, cerca de 40 % a mais). Isso é compatível com parte da
queda em FALHA, mas não prova a causa: não medimos isso separadamente. O que os dados mostram é que a persistência também
caiu no teste, o que sugere um trecho de tempo mais difícil, e não só um modelo pior.

## 9. Limitações

1. **Fluxo que o modelo não viu.** A contagem é por código. Os **79 fluxos com baseline suficiente** aparecem nos três
   blocos (treino, validação e teste). **Nenhum fica fora do treino** (0 de 79). Os 2 fluxos com baseline insuficiente
   não estão no dataset rotulado, e o 82º fluxo do Silver não tem ficha de baseline. Logo, **este teste não responde se o
   modelo generaliza para um fluxo novo**: ele mede os mesmos caminhos que o modelo treinou, em outro trecho do tempo.
   Como a seção 3 do diário pede, a conta não foi forçada: a limitação está declarada aqui e no `resultado.json`.
2. **Baseline fixo** (diário, seção 4): o normal de cada caminho é a mediana das primeiras 108 horas. Se a rota mudar
   depois, o baseline não acompanha, e o modelo passa a medir contra um normal que já não existe.
3. **Rajada curta** (diário, seção 4): cada medição é a média de uma rajada curta de pings. Com poucos pings, o jitter é
   estimado mal, e isso pesa nas colunas de jitter.
4. **Anchors não são a rede de um campus** (diário, seção 4): as sondas são Anchors do RIPE Atlas. O resultado é sobre
   caminhos entre sondas públicas, não sobre a rede de um campus.
5. **Rótulo é política**: o alvo é a regra da RFC com o piso de 30 % de aumento na linha 3 (decisão do dono, 09/10/2026).
   O modelo aprende essa definição, não falhas reais de equipamento.
6. **Poucos fluxos e poucos dias**: 79 caminhos e 7 dias. O IC reamostra fluxos, e mesmo assim o limite inferior é
   pequeno (+0,0168).
7. **A árvore ajustada legível não foi medida no teste.** Ela é exportada à parte (`arvore_ajustada.joblib`, regras em
   `data/modelo/regras_arvore_ajustada.txt`). Também não foi medido o XGBoost. Se o grupo quiser a árvore como referência
   no teste, ela só entra como referência declarada, e isso não foi feito.
8. **Escolha pela regra, não pelo maior F1**: a floresta foi escolhida pela regra do empate. O XGBoost tinha F1 macro
   0,0029 maior na validação, dentro da tolerância. No teste não se sabe qual dos dois iria melhor.
9. **Dicionário das colunas**: o dicionário v0.4 que o diário pede não está no repositório. A descrição das 10 colunas
   na ficha é a do grupo, e precisa ser conferida pelo dono (ver a ficha).

## 10. Decisões e fontes

**Decisões do teste (já tomadas e registradas):**

- O modelo medido é o arquivo `modelo_final.joblib`, com SHA-256 `197579cba624b57c2d70c07e7db40524fc09d36ebfb7b9c083715e2d3809e48d`.
- A declaração segue a regra 4 da spec, com a leitura do dono de 10/10/2026: **limite inferior do IC maior que zero**.
- O caso 1 usa `maior_rtt=True` (espelha o caso 1 da validação), decisão do dono.
- O teste foi aberto **uma vez**. A trava `TESTE_ABERTO.json` está `concluido` e não foi apagada. Uma segunda abertura é
  recusada pelo código.

**Verificações feitas depois da abertura:**

- Antes da redação deste relatório, nenhum arquivo de `src/`, `web/dados/` ou `data/modelo/` (exportado e comparação)
  tinha mudado depois de 14:49 (conferido por `find -newer` sobre a trava).
- O SHA-256 de `modelo_final.joblib` continua o mesmo, e o de `escolha.json` (`7c4645…`) é o que o `resultado.json`
  registrou.

**Fontes dos números:**

| Número | Fonte |
|---|---|
| Matriz 3×3 (teste, RF e persistência) | `data/modelo/teste/matriz_teste.csv` |
| Precisão, recall, F1 por classe, F1 macro, balanced accuracy, acurácia, transições, acerto por futuro igual/muda | `data/modelo/teste/metricas_teste.csv` |
| IC do ganho, declaração, distribuição de classes, fluxos, limitação | `data/modelo/teste/resultado.json` e `ic_ganho_teste.csv` |
| Casos com fluxo e horário | `data/modelo/teste/casos_teste.txt` |
| Validação (F1, recall, IC, matriz) | `data/modelo/comparacao/comparacao_modelos.csv`, `matriz_comparacao.csv`, `ic_pareado.csv` |
| Validação, precisão de FALHA | calculada de `matriz_comparacao.csv` (linha FALHA sobre a coluna FALHA) |
| Intervalos de bloco e instantes | `data/gold/contagem_classes.csv` (leitura humana do Gold; não lê linhas do teste) |
| Trava e data da abertura | `data/modelo/teste/TESTE_ABERTO.json` |

## 11. Como reproduzir (e o que não se repete)

Reproduzir a **validação** e o **ensaio** é possível: `uv run python -m preditor comparar`, `exportar` e
`teste --ensaio`, nessa ordem (ver a ficha, seção "Como reproduzir").

O **teste não se repete**: `teste --abrir-o-teste` recusa com `TESTE_ABERTO.json` presente. Apagar a trava para rodar de
novo é decisão do dono e precisa ser registrada, e não é o caminho deste relatório. Os números do teste estão nos
arquivos de `data/modelo/teste/`, que são o registro da execução.

## 12. Pendências

- **Dicionário v0.4.** O dono precisa confirmar as descrições das 10 colunas da ficha. Se a professora forneceu o
  arquivo, ele entra no lugar delas.
- **O dono leva o resultado ao diário da Tarefa 5** (o diário tem campos em branco, e o preenchimento é do grupo).
- **Commit.** Nada foi commitado; só se o dono pedir.
