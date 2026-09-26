# RFC: Preditor de degradação de rede com RTT normalizado

> Um RFC formaliza o problema, o contrato dos dados e o critério de decisão antes de se investir no classificador. Este documento escolhe a **representação** do fenômeno (RTT normalizado por fluxo). A família do algoritmo (árvore, floresta, boosting ou outro) fica para a etapa de modelagem, escolhida na validação.

---

## 1. Resumo

O projeto constrói um classificador de três estados — **OK**, **RISCO** e **FALHA** — para medições ICMP de pares origem–destino. O estado descreve o afastamento do fluxo em relação ao seu próprio comportamento normal, estimado num período anterior e depois congelado.

A distância da rota entra na física do RTT e na chance de haver mais saltos, congestionamento e perda. Ela não entra na classe. Um RTT de 180 ms pode ser o normal de um caminho transoceânico saudável; um salto de 25 ms para 58 ms pode ser degradação num caminho curto. O modelo aprende esse desvio, em conjunto com perda, jitter relativo, timeouts e persistência.

---



## 2. Contexto e motivação

Uma rede em operação precisa distinguir três coisas que aparecem juntas numa série de ping:

1. **Latência estrutural.** A propagação na fibra tem limite físico. Mais quilômetros e mais roteadores aumentam o RTT mesmo com o caminho saudável. Cruzar o Atlântico em cerca de 150–200 ms é atraso esperado, não defeito. O mesmo vale para os caminhos longos já medidos neste projeto (BR→JP com mediana de 277 ms, BR→IN e BR→ZA em torno de 340 ms).
2. **Degradação.** O caminho continua respondendo, mas piorou em relação a si mesmo: RTT sobe além da variação típica, o jitter deixa de ser estável ou surge perda moderada e persistente. Causas típicas: congestionamento, enlace saturado, hardware no limite, interferência.
3. **Indisponibilidade.** Perda total ou ausência persistente de resposta. É falha independentemente da distância.
4. **Mudança de rota.** O encaminhamento troca de caminho (tromboning, failover, novo trânsito). O RTT muda de patamar e permanece estável, com perda e jitter baixos. O enlace novo pode estar saudável; o que envelheceu foi o baseline.

Tratar “RTT alto” como falha ensina geografia. Na regra absoluta antiga (OK ≤ 50 ms, FALHA > 100 ms), caminhos longos estáveis viravam FALHA permanente e um enlace curto que quadruplicasse a latência ainda podia sair como OK. No Período B desta coleta, 22.685 janelas que seriam FALHA absoluta são OK no critério relativo, e 4.135 que seriam OK absoluta são FALHA relativa.

O usuário do alerta é quem opera a rede (campus, provedor ou NOC). O alerta apoia a decisão de investigar o enlace agora, observar, ou recalibrar o “normal” porque o caminho mudou.

---



## 3. Problema e evento a ser previsto


| Pergunta                     | Resposta                                                                                                                                                                                                                                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qual evento será previsto?   | Degradação ou indisponibilidade de um fluxo ICMP em relação ao baseline daquele fluxo.                                                                                                                                                                                                            |
| Como será definida a classe? | Regra híbrida, auditável, relativa ao fluxo: desvio robusto do RTT, aumento relativo, jitter relativo, perda e persistência. Perda de 100% ou ausência persistente de RTT é FALHA mesmo sem baseline. Os rótulos são operacionais: o modelo reproduz essa política, não um ticket de equipamento. |
| Qual é o horizonte?          | Dois alvos, em arquivos separados. **Detector:** `status_atual` da janela corrente. **Preditor:** `status_futuro` em 12 minutos (três intervalos do mesh, de 240 s). O preditor só é útil se superar a persistência do estado atual.                                                              |
| Qual é a unidade de análise? | Uma medição de um fluxo, enriquecida com a janela causal recente do mesmo fluxo. O fluxo é `fluxo_id = probe_id                                                                                                                                                                                   |


Estados:


| Classe    | Significado operacional                                                                    |
| --------- | ------------------------------------------------------------------------------------------ |
| **OK**    | RTT, jitter e perda compatíveis com o normal daquele fluxo.                                |
| **RISCO** | Aumento relevante e persistente de latência, jitter ou perda, ainda sem indisponibilidade. |
| **FALHA** | Desvio extremo e persistente, perda elevada ou ausência de resposta.                       |


Há um quarto estado **operacional**, fora do alvo supervisionado de três classes: **RECALIBRAR**. Ele marca mudança estável de patamar de RTT (rota nova saudável). Não é falha e não deve ser ensinado como FALHA.

---



## 4. Escopo


| Pergunta         | Resposta                                                                                                                                                                                                                                                                                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Recorte          | Overlay lógica sobre o *Anchoring Mesh* público do RIPE Atlas (ping IPv4). 12 rotas de desenho (intra-país, regional e longa), 21 IPs de destino, 67 fluxos. A classe não usa o país nem a categoria geográfica.                                                                                                                                                          |
| Período          | 06/09/2026 04:32 UTC a 20/09/2026 04:32 UTC. Sete dias de baseline (Período A) e sete dias posteriores de dataset (Período B), sem sobreposição.                                                                                                                                                                                                                          |
| Dentro do escopo | Leitura de medições já existentes; baseline congelado por fluxo; features relativas; rótulos OK / RISCO / FALHA; split temporal e split por fluxo; comparação com a persistência; contrato para um monitor local futuro com o mesmo esquema.                                                                                                                              |
| Fora de escopo   | Criar medições (`POST`) ou gastar créditos RIPE Atlas. IPv6, traceroute e HTTP na mesma coluna de latência. Limiar global de RTT (50 ms, 100 ms ou qualquer outro). País, IP ou `rota_id` como feature do modelo. Balancear o dataset escolhendo rotas que “fabricam” uma classe. Preencher RTT ausente com 0. Split aleatório de linhas. Escolher o algoritmo neste RFC. |


---



## 5. Usuários e decisão apoiada

O alerta é para quem administra o enlace monitorado. Com **FALHA**, a ação é investigar perda, timeout ou desvio extremo persistente. Com **RISCO**, a ação é observar e priorizar, sem tratar o evento como queda. Com **OK**, nenhuma intervenção. Com **RECALIBRAR**, a ação é abrir um novo período de baseline para o fluxo e não abrir chamado de falha só porque o RTT mudou de patamar.

O mesmo contrato vale para o `log_rede.csv` da instituição, depois de um aquecimento de pelo menos 1.500 amostras válidas naquele fluxo. Sem esse aquecimento não há mediana confiável, e o modelo normalizado não opera.

---



## 6. Dados e fontes


| Fonte                                                     | O que fornece                                                                                           | Papel                                      |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| RIPE Atlas v2, mesh de Anchors, ping IPv4 (`GET` público) | Timestamp, `probe_id`, destino, RTT da rajada (tipicamente 3 pacotes), enviados/recebidos, timeout      | Medição bruta. Feature e insumo do alvo.   |
| Período A, por `fluxo_id`                                 | Mediana e MAD do RTT, jitter típico, perda típica, cobertura                                            | Baseline congelado. Não é linha de treino. |
| Período B                                                 | Features absolutas e relativas, janela de cerca de 20 minutos, `status_atual`, `status_futuro` (12 min) | Dataset do detector e do preditor.         |


Volume observado: 336.326 registros brutos; 64 fluxos com baseline suficiente (mínimo de 1.500 amostras; 3 fluxos BR→BR para `170.81.100.114` excluídos, sem mediana inventada); 160.317 linhas em `dataset_monitoramento.csv` e 159.996 em `dataset_predicao.csv`. No Período B a distribuição relativa é 76,8% OK, 5,2% RISCO e 18,0% FALHA. Esse desbalanceamento é o fenômeno: a malha passa a maior parte do tempo no próprio normal.

Cadência nativa do mesh: 240 segundos. Jitter da amostra é o desvio-padrão dos RTTs da rajada somente quando há pelo menos duas respostas; com 0 ou 1 resposta o jitter fica vazio.

O material sobre distância das rotas recomenda, para um agente local, rajadas de 10 a 20 pings espaçados de 1 segundo a cada 5 minutos, jitter no sentido da RFC 3550 e um baseline de cerca de 5 dias. Esse desenho é o contrato do **monitor local futuro**. A coleta deste projeto não o replica: o mesh já amostra a cada 4 minutos com 3 pacotes, a leitura é somente `GET`, e um ping contínuo a cada segundo criaria carga inútil. Cinco dias são o piso citado para um perfil dinâmico; sete dias foram adotados para cobrir um ciclo semanal em cada período e ficar acima de 1.500 amostras por fluxo.

**Dicionário de dados:** a ser versionado junto com `COLUNAS_MODELO`. País, endereço e identificador de rota permanecem na auditoria e saem da matriz do modelo.

---



## 7. Custo dos erros


| Tipo de erro            | O que significa                                                                      | Consequência                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| Falso negativo de FALHA | Indisponibilidade ou desvio extremo persistente classificado como OK ou RISCO        | O enlace degrada sem investigação. É o erro mais grave.                              |
| Falso negativo de RISCO | Início de saturação tratado como OK                                                  | Atraso na priorização. Grave, e mais difícil porque RISCO é a classe rara (5,2%).    |
| Falso positivo de FALHA | Rota longa saudável, pico isolado ou mudança estável de caminho rotulados como queda | Fadiga de alerta e chamado indevido. Foi o modo de falha da regra absoluta.          |
| Falso positivo de RISCO | Oscilação normal do fluxo disparando alerta                                          | Ruído operacional. A persistência (2 de 5 medições) existe para cortar pico isolado. |


A métrica principal é o **F1 macro**, com recall de FALHA e a confusão RISCO↔FALHA reportados à parte. Acurácia isolada é enganosa com 77% de OK. O limiar de decisão do modelo, quando houver probabilidade, escolhe-se na validação; o teste é usado uma vez.

---



## 8. Abordagem proposta

O tipo de modelo adequado é o **Modelo RTT normalizado**: um único modelo treinado com muitos fluxos, cada um descrito pelo desvio em relação ao seu baseline. Um modelo por fluxo exigiria série e manutenção próprias para cada caminho. Um modelo único com RTT absoluto confunde distância com falha.

Caminho, sem escolha de algoritmo:

ingestão do mesh (JSON bruto preservado) → Período A só para baseline → congelamento → features relativas no Período B → rótulo híbrido → split temporal e split por fluxo → baselines de regra (persistência e classe majoritária) → um `Pipeline` (pré-processamento + classificador) → limiar na validação → model card.

### 8.1 O que a distância explica

A distância aumenta a chance de falha de entrega porque o pacote atravessa mais saltos, acumula atraso de propagação e fica exposto a mais pontos de congestionamento. Em meio sem fio ou em cabo fora do padrão, a distância também degrada o sinal. Congestionamento, cabo, conector, interferência e hardware continuam sendo causas mesmo em rota curta.

Por isso o RTT médio bruto não classifica. Ele mistura o comprimento do caminho com o incidente. O que classifica é o comportamento estatístico do RTT **daquele** fluxo, junto com perda e instabilidade (jitter), sustentados no tempo.

Exemplos que o modelo tem de tratar como OK quando estáveis:


| Caminho                                         | RTT normal observado ou de referência | Leitura                                                                     |
| ----------------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------- |
| Intra-país curto (DE→DE, AR→AR)                 | mediana 14 ms e 10 ms                 | Normal baixo.                                                               |
| BR→BR                                           | mediana 50 ms                         | Normal do continente; variação interna existe.                              |
| BR→EUA (referência física do material de rotas) | cerca de 110–200 ms                   | Atraso de cabo submarino, saudável se estável.                              |
| BR→JP / BR→IN / BR→ZA                           | medianas 277 ms, 339 ms e 344 ms      | Normal do fluxo. No rótulo relativo, BR→IN e BR→ZA são majoritariamente OK. |


O caso didático do material de rotas (SP→Espanha→RJ, RTT estável perto de 180 ms, contra 5–15 ms no caminho direto) é mudança de encaminhamento, tratada na seção 8.5, não como falha de hardware.

### 8.2 Baseline por fluxo

O baseline é uma ficha por `fluxo_id` (`probe_id|dst_addr`), calculada só no Período A e depois congelada. O Período B não entra nessa conta e não é rotulado com dados de A.


| Passo | O que fazer                                                                                                                                                                  |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | Separar o fluxo. Ordenar as medições pelo timestamp.                                                                                                                         |
| 2     | Cortar o tempo. Período A: 06/09/2026 04:32 UTC até 13/09/2026 04:32 UTC (7 dias). Período B: o instante seguinte até 20/09/2026 04:32 UTC. Sem amostra nos dois períodos.   |
| 3     | Marcar RTT válido. Entra na ficha só a medição com RTT presente. RTT ausente e perda de 100% ficam de fora da mediana e do MAD. Continuam no dataset como evento de timeout. |
| 4     | Exigir volume. Menos de 1.500 RTT válidos no Período A: o fluxo é `baseline_insuficiente` e não recebe classe.                                                               |
| 5     | Calcular a ficha e gravar uma linha em `baseline_por_fluxo.csv`. Não recalcular com o Período B.                                                                             |



| Campo da ficha  | Fórmula, só com o Período A                                               |
| --------------- | ------------------------------------------------------------------------- |
| `mediana`       | mediana dos RTT válidos                                                   |
| `MAD`           | mediana(                                                                  |
| `jitter_tipico` | mediana do jitter nas medições com jitter presente                        |
| `perda_tipica`  | mediana de `perda_pct` em todas as medições do período, inclusive timeout |
| `prop_resposta` | medições com RTT válido / medições do período                             |


Essa ficha é o “normal” do fluxo. Um RTT de 340 ms pode ser a mediana de BR→ZA e, nesse caso, é o valor de referência, não um defeito. A rotulagem da seção 8.4 só começa depois que a ficha existe.

A média e o desvio-padrão clássicos, sugeridos no material de rotas como “média ± 1, 2 ou 3 desvios”, descrevem a mesma ideia (uma janela de normalidade própria da rota). Eles são substituídos por mediana e MAD porque picos — justamente os incidentes — inflam a média e o desvio e alargam o “normal” até engolir a falha. O escore robusto é a versão estável da regra dos três sigmas:

z_{\text{robusto}} = \frac{x - \operatorname{mediana}}{1{,}4826 \times \mathrm{MAD}}

O fator 1,4826 torna o MAD comparável ao desvio-padrão quando a distribuição é aproximadamente normal. Assim, os gatilhos “cerca de 2 desvios” e “cerca de 3 desvios” do material de rotas sobrevivem, sem herdar a sensibilidade da média.

Se MAD = 0 e a latência corrente é a mediana, z = 0. Caso contrário usa-se IQR/1,349 ou um piso de 1 ms, para não dividir por zero.

### 8.3 Features

Cada linha do modelo leva o vetor relativo, não o mapa:

X = [\text{latência relativa}, z_{\text{robusto}}, \text{perda}, \text{jitter relativo}, \text{timeouts}, \text{tendência}, \text{persistência}]

Definições:

```text
latencia_relativa   = latencia_atual / mediana_A
aumento_latencia_pct = (latencia_atual - mediana_A) / mediana_A * 100
z_robusto           = (latencia_atual - mediana_A) / (1,4826 * MAD_A)
jitter_relativo     = jitter_atual / jitter_tipico_A
```

Uma razão de latência igual a 1,0 é “no normal” tanto para DE→DE quanto para BR→ZA. Tendência e persistência olham as últimas janelas do mesmo fluxo (cerca de cinco medições, ~20 minutos). País, IP e identificador de rota ficam de fora: a árvore aprenderia “Japão = FALHA” e o contrato quebraria no log local.

RTT ausente permanece vazio, com `timeout_atual = 1`. Zero milissegundo seria um OK falso e ainda contaminaria qualquer média futura.

### 8.4 Regra de rotulagem

A classe nasce de uma política explícita, não de agrupamento sobre o RTT. O aluno calcula as métricas e aplica a primeira linha que for verdadeira. Não há empate: FALHA ganha de RISCO, e RISCO ganha de OK.

**Métricas, calculadas por fluxo com o baseline do Período A congelado.**


| Métrica           | Fórmula                                                                           | Valor que entra na regra |
| ----------------- | --------------------------------------------------------------------------------- | ------------------------ |
| `mediana`         | mediana dos RTT válidos do Período A                                              | ms                       |
| `MAD`             | mediana(                                                                          | RTT − mediana            |
| `z_robusto`       | (RTT atual − mediana) / (1,4826 × MAD)                                            | número sem unidade       |
| `aumento_pct`     | (RTT atual − mediana) / mediana × 100                                             | %                        |
| `jitter_relativo` | jitter atual / jitter típico do baseline                                          | número sem unidade       |
| `perda_pct`       | (enviados − recebidos) / enviados × 100                                           | %                        |
| `timeout_atual`   | 1 se não há RTT ou `perda_pct` = 100; senão 0                                     | 0 ou 1                   |
| `n5_timeout`      | quantos `timeout_atual` = 1 nas últimas 5 medições deste fluxo, incluindo a atual | 0 a 5                    |
| `n5_aumento80`    | quantas das últimas 5 têm `aumento_pct` > 80                                      | 0 a 5                    |
| `n5_risco`        | quantas das últimas 5 cumprem o critério de risco da linha 5                      | 0 a 5                    |


Casos de conta, para o resultado não depender de quem calcula:


| Situação                                  | O que fazer                                                                               |
| ----------------------------------------- | ----------------------------------------------------------------------------------------- |
| RTT ausente                               | Não calcular `z_robusto` nem `aumento_pct`. `timeout_atual` = 1. Não preencher RTT com 0. |
| MAD = 0 e RTT atual = mediana             | `z_robusto` = 0                                                                           |
| MAD = 0 e RTT atual ≠ mediana             | Trocar o denominador por max(IQR / 1,349, 1 ms)                                           |
| Jitter atual vazio (menos de 2 respostas) | O critério de jitter não dispara                                                          |
| Jitter típico = 0 e jitter atual = 0      | `jitter_relativo` = 1                                                                     |
| Jitter típico = 0 e jitter atual > 0      | Tratar como `jitter_relativo` ≥ 3                                                         |
| Menos de 1.500 RTT válidos no Período A   | Não rotular. Fluxo `baseline_insuficiente`                                                |


**Regra de rótulo. Parar na primeira linha verdadeira.**


| Ordem | Classe    | Métrica                                                                                                          | Limiar exato                                                       |
| ----- | --------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| 1     | **FALHA** | `perda_pct`                                                                                                      | ≥ 10 nesta medição (inclui 33%, 67% e 100% da rajada de 3 pacotes) |
| 2     | **FALHA** | `n5_timeout`                                                                                                     | ≥ 3                                                                |
| 3     | **FALHA** | `z_robusto`                                                                                                      | ≥ 3,5 nesta medição, com RTT presente                              |
| 4     | **FALHA** | `n5_aumento80`                                                                                                   | ≥ 2                                                                |
| 5     | **RISCO** | nesta medição, pelo menos um destes: `2 ≤ z_robusto < 3,5`, ou `30 ≤ aumento_pct ≤ 80`, ou `jitter_relativo ≥ 3` | e `n5_risco` ≥ 2                                                   |
| 6     | **OK**    | nenhuma linha anterior                                                                                           | pico isolado também fica OK                                        |


Leitura das linhas 5 e 6: um único desvio moderado não vira RISCO. Dois desvios moderados nas últimas cinco medições viram RISCO. `z_robusto` ≥ 3,5 vira FALHA já na medição corrente. Perda de um pacote em três (≥ 33%) vira FALHA na hora, porque 33 ≥ 10.

`status_absoluto` (OK ≤ 50 ms, FALHA > 100 ms) não entra nesta tabela.

Regra crítica, independente do baseline e alinhada ao material de rotas (“perda é o primeiro gatilho”):

```text
perda = 100% ou ausência persistente de RTT  =>  FALHA
```

A persistência existe porque uma rajada isolada é ruído. Um pico não sustenta FALHA.

Os limiares absolutos de perda do material de rotas (estável até 0,5%, risco de 0,5% a 2%, falha acima de 2%) e de jitter (estável abaixo de 10–20 ms, risco de 20–50 ms, falha acima de 50 ms) descrevem bem uma rajada de 15 pacotes num enlace que se quer apto a voz e vídeo. Eles não são o contrato desta coleta, por dois motivos de medida:

- Com 3 pacotes ICMP, a perda observável é 0%, 33%, 67% ou 100%. Faixas de 0,5% e 2% não aparecem na amostra.
- Um teto global de jitter em milissegundos repete o erro do teto global de RTT: o jitter típico cresce com o caminho. O que entra no rótulo é o jitter dividido pelo jitter do próprio baseline.

Quando o monitor local passar a usar rajadas de 10 a 20 pacotes, a perda pode descer à granularidade do material de rotas, sempre comparada também à perda típica do fluxo. O espírito permanece: perda e instabilidade disparam alerta; o valor bruto do RTT não dispara sozinho.

A regra absoluta antiga permanece só em `status_absoluto`, para auditoria.

No Período B, o mecanismo dominante de FALHA deixou de ser “RTT > 100 ms”. Passou a ser desvio robusto (17.694 linhas), perda ≥ 10% (10.885) e timeout (9.877). O jitter relativo passou a marcar RISCO (5.088 linhas).

### 8.5 Mudança de rota

O material de rotas acrescenta um caso que o baseline fixo de sete dias não cobre. Se o RTT muda de patamar e **permanece estável**, com perda próxima de zero e jitter baixo por uma janela longa (no material, mais de uma hora; na cadência de 4 minutos, da ordem de 15 amostras), a evidência é de novo encaminhamento, não de saturação.

Critério operacional proposto:

```text
se |z_robusto| alto
   e perda próxima do normal do fluxo
   e jitter_relativo baixo
   por uma janela sustentada (ordem de 1 hora)
então RECALIBRAR
senão aplicar a regra híbrida da seção 8.4
```

RECALIBRAR descarta o uso da ficha antiga para aquele fluxo e abre um novo período de baseline (o material sugere 24–48 h nesse caso excepcional; o piso de 1.500 amostras válidas continua valendo antes de voltar a classificar). Queda de RTT estável (fim de um tromboning) segue a mesma regra. Essas janelas não entram como FALHA no treino: ensinar “patamar novo e estável = pane” recria a confusão entre distância e defeito.

O dataset já rotulado do Período B ainda não separa esse estado. Introduzir a coluna é decisão da próxima revisão de rótulos, feita só com o passado de cada fluxo, sem usar o período de teste.

O fluxo é identificado pelo par probe e endereço de destino, não por um nome DNS re-resolvido a cada ciclo. Troca de IP é outro fluxo e exige baseline próprio.

### 8.6 Como o modelo deve ser lido

O modelo não aprende que RTT alto significa falha. Aprende que risco ou falha ocorrem quando o comportamento recente do fluxo se afasta do normal daquele mesmo fluxo, com perda, instabilidade ou ausência de resposta, e que um patamar novo porém estável pede recalibração.

Para um fluxo nunca visto, o procedimento é de calibração, não de retreino: observa-se o período inicial, congela-se a ficha e só então se aplicam as features relativas. Sem esse período o modelo não opera naquele fluxo.

---



## 9. Avaliação

Dois protocolos, com resultados separados.

**Protocolo A — tempo.** Dentro de cada fluxo do Período B, o passado treina, um bloco posterior valida e o bloco mais recente testa. Sem sorteio de linhas. Janelas com lag respeitam uma folga entre os blocos. Qualquer imputação, escala ou balanceamento aprende-se só no treino. Proporção de partida 50% / 20% / 30% dentro de B, ajustada para respeitar a cronologia e o suporte de RISCO.

**Protocolo B — fluxos novos.** Grupos inteiros por `fluxo_id` (GroupShuffleSplit ou GroupKFold, semente fixa). Nenhum fluxo de teste aparece no treino. O baseline do fluxo de teste sai só do período inicial dele. O conjunto de teste precisa continuar cobrindo caminho curto e caminho longo; o hold-out da rota BR→JP faz parte dessa checagem.

Métricas: matriz 3×3, precisão, recall e F1 por classe, F1 macro, balanced accuracy, e o mesmo corte por fluxo. Comparar o preditor de 12 minutos com a regra que copia `status_atual`. Na referência já observada, essa persistência fica em torno de 0,70 de F1 macro e uma árvore em torno de 0,65: sem ganho sobre a persistência, o artefato é um detector, e o nome preditor não se sustenta.

---



## 10. Riscos e limitações

- Rótulos heurísticos. O modelo aprende a política de degradação, não uma falha confirmada em log de roteador.
- Anchors são melhor provisionados que um CPE de campus. Perda e jitter de último quilômetro ficam sub-representados. O log local continua necessário para a rede da instituição.
- Amostras do mesmo fluxo a cada 4 minutos são autocorrelacionadas. Os dois protocolos de split são a mitigação; um split aleatório inflaria o resultado.
- Rajada de 3 pacotes estima mal o jitter. O jitter relativo ainda assim passou a marcar RISCO; a RFC 3550 fica reservada ao agente local, quando a rajada tiver pacotes suficientes.
- Baseline fixo de 7 dias não acompanha deriva lenta nem troca de rota. A seção 8.5 é a correção prevista; até lá, uma mudança estável de caminho pode ser rotulada como desvio extremo.
- Sete mais sete dias cobrem um ciclo semanal em cada período, não a estabilidade entre semanas.
- A 12 minutos o futuro ainda é, em grande parte, o estado atual.
- Três fluxos sem RTT válido foram excluídos em vez de receber mediana inventada.
- RISCO é raro. F1 macro e o suporte dessa classe precisam aparecer no relatório; rebalancear por rota ensinaria o mapa de novo.

---



## 11. Critérios de sucesso

1. Nenhum fluxo de teste contribui para o próprio baseline, e nenhuma feature usa país, IP ou rota.
2. No teste temporal, o detector separa OK, RISCO e FALHA com F1 macro acima da classe majoritária, e o recall de FALHA fica explícito.
3. O preditor de 12 minutos supera a persistência de `status_atual` no mesmo teste. Se não superar, a entrega declara o sistema como detector.
4. No teste por fluxos novos, depois do aquecimento, um caminho longo estável não colapsa em FALHA e um caminho curto degradado não colapsa em OK.
5. Exemplos auditáveis: BR→JP (ou BR→ZA) estável como OK; um fluxo curto com aumento persistente como RISCO ou FALHA; timeout persistente como FALHA; um patamar novo e estável encaminhado a RECALIBRAR quando essa regra estiver ativa.
6. Model card e dicionário alinhados às colunas que o `Pipeline` de fato consome.

---



## 12. Alternativas consideradas


| Alternativa                                                                                               | Consequência que levou à rejeição                                                                                                                                                                                   |
| --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Limiar global de RTT (50/100 ms, ou “acima de 100 ms é falha”)                                            | A classe vira distância. Rota longa estável fica sempre em FALHA; rota curta pode degradar centenas de por cento e continuar OK.                                                                                    |
| Um modelo só com RTT absoluto misturando todos os fluxos                                                  | O algoritmo usa o comprimento do caminho como atalho para a classe.                                                                                                                                                 |
| Um modelo separado por fluxo                                                                              | Válido para um único enlace, e caro em dados e manutenção para um preditor reutilizável.                                                                                                                            |
| Média e desvio-padrão do material de rotas como estatística do baseline                                   | A intuição (janela de 2 e 3 sigmas) é a certa; a média e o desvio são arrastados pelos picos que se quer detectar. Mediana e MAD preservam a mesma escala via o fator 1,4826.                                       |
| Jitter absoluto de 20/50 ms e perda de 0,5/2% como lei universal                                          | Jitter absoluto reintroduz a distância. Perda de 0,5% não é observável em rajada de 3 pacotes. Ficam como meta do agente local, relativas ao fluxo.                                                                 |
| Baseline de 5 dias com rajadas de 15 pings a cada 5 minutos, ping local a um único alvo (RJ–SP ou BR–EUA) | Adequado a um app de um enlace. Esta coleta precisa de muitos fluxos, série já existente e zero crédito: mesh público, 7+7 dias, 240 s. O desenho local permanece como contrato futuro, com o mesmo vetor relativo. |
| Preencher timeout com 0 ms                                                                                | 0 ms parece latência excelente e polui a média.                                                                                                                                                                     |
| k-means sobre o RTT, ou percentil global do lote                                                          | O alvo deixa de ser uma política operacional e passa a depender do lote futuro, que o monitor não tem.                                                                                                              |
| Split aleatório de linhas                                                                                 | Janelas vizinhas do mesmo fluxo caem em treino e teste.                                                                                                                                                             |
| Probes aleatórios do mesh, ou superamostrar rotas longas para “balancear” FALHA                           | Com limiar absoluto, cerca de 85% virava FALHA. Com limiar relativo, rota longa estável é justamente o OK que o modelo precisa ver.                                                                                 |
| IPv4 e IPv6 na mesma coluna `latencia_ms`                                                                 | Dois regimes físicos no mesmo número.                                                                                                                                                                               |
| Medições próprias no RIPE Atlas                                                                           | Crédito, série curta e viés da sonda de quem coleta.                                                                                                                                                                |


---



## 13. Perguntas em aberto

1. A coluna RECALIBRAR entra numa re-rotulagem do Período B antes do treino, ou só no monitor em operação? Até a resposta, o treino usa as três classes já gravadas e documenta o viés de mudança de rota.
2. Os limiares (z = 2 e 3,5, aumento de 30% e 80%, jitter relativo ≥ 3, perda ≥ 10%) podem ser ajustados na validação. O teste não escolhe limiar.
3. Baseline móvel causal (somente os 14 ou 28 dias anteriores a t) substitui a ficha fixa quando houver série mais longa que 7+7.
4. Qual classificador entra no `Pipeline` decide-se na validação, contra persistência e classe majoritária.
5. No agente local, o tamanho da rajada (10 a 20 pacotes) e o uso da RFC 3550 dependem de uma coleta própria; não alteram o contrato do CSV já fechado.

---



## 14. Encadeamento


| Etapa             | Produz                                                                                          | A etapa seguinte usa           |
| ----------------- | ----------------------------------------------------------------------------------------------- | ------------------------------ |
| Coleta            | JSON bruto, registros dos Períodos A e B, sem classe na ingestão                                | Este bruto                     |
| Baseline e rótulo | `baseline_por_fluxo.csv`, `dataset_monitoramento.csv`, `dataset_predicao.csv`, regra versionada | Estes rótulos e estas features |
| Divisão           | Protocolos A e B, mapa de `fluxo_id`, auditoria de vazamento                                    | O mesmo split em todo retreino |
| Modelo            | `Pipeline`, comparação com persistência, limiar na validação, model card                        | —                              |


Não se rotula o período que estimou o baseline. Não se sorteia linha para o teste final.

---




|     |
| --- |
|     |


