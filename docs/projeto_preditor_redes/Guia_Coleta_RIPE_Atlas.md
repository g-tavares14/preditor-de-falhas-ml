# Guia da coleta — RIPE Atlas, fluxos e baseline

Leitura da Tarefa 1 e da Tarefa 2. Os exemplos não recebem classe. OK, RISCO e FALHA estão na Tarefa 2.

API: [manual REST v2](https://atlas.ripe.net/docs/apis/rest-api-manual/introduction/) e [formato do resultado](https://atlas.ripe.net/docs/apis/measurement-result-format/). Base: `https://atlas.ripe.net/api/v2/`.

---

## 1. Glossário

| Termo | Definição |
|---|---|
| **RIPE Atlas** | Sondas do RIPE NCC que medem a Internet e publicam o resultado. |
| **API v2** | Leitura HTTP. Neste projeto só `GET`. |
| **Probe** | Sonda que envia a medição. Chave estável: `prb_id`. O IP em `from` muda com NAT. |
| **Anchor** | Probe de datacenter, endereço estável. Origem e alvo do mesh. |
| **Measurement** | Campanha com `msm_id`, tipo e `af` (4 ou 6). `Ongoing` = em andamento. |
| **Anchoring mesh** | Ping IPv4 automático entre Anchors, a cada 240 s. Fonte deste projeto. |
| **Result** | Uma execução: um probe, um instante, um alvo. `GET /api/v2/measurements/{msm_id}/results/`. |
| **`probe_ids`** | Filtro: lista de `prb_id`. Sem ele a API devolve a malha inteira. |
| **`start` / `stop`** | Recorte de tempo, em Unix. Separa dias e os Períodos A e B. |
| **Crédito** | Custo de criar medição (`POST`). `GET` público não gasta crédito e não pede chave. |
| **`sent` / `rcvd`** | Pacotes enviados e respondidos. No mesh, `sent` costuma ser 3. |
| **`avg`, `min`, `max`** | RTT da rajada, em ms. Sem resposta, `avg` não existe. |
| **`result[].rtt`** | RTT de cada pacote que voltou. Base do jitter. |
| **`dst_addr`** | IP do alvo. Chave do destino no fluxo. |
| **`dst_name`** | Nome do alvo. O fluxo usa o IP: o DNS pode trocar o endereço. |
| **`timestamp`** | Epoch da amostra. Guardar em UTC. |

Consulta que filtra:

```text
GET /measurements/?type=ping&target={nome do anchor}     → acha o msm_id
GET /measurements/{msm_id}/results/?probe_ids=...&start=...&stop=...
```

`/anchor-measurements/` e `/probes/?measurement=` ignoram filtro de alvo e de tipo.

---

## 2. Fluxo

Par estável quem mede → quem é medido, no tempo.

```text
fluxo_id = probe_id | dst_addr
```

| timestamp (UTC) | fluxo_id | sent | rcvd | avg (ms) |
|---|---|---|---|---|
| 06/09 04:32 | `1001\|200.0.0.10` | 3 | 3 | 48 |
| 06/09 04:36 | `1001\|200.0.0.10` | 3 | 3 | 51 |
| 06/09 04:40 | `1001\|200.0.0.10` | 3 | 0 | vazio |

RTT vazio permanece vazio. Não gravar 0.

| Situação | Fluxo |
|---|---|
| Mesmo probe, mesmo destino | O mesmo |
| Outro probe, mesmo destino | Outro (`1002\|200.0.0.10`) |
| Mesmo probe, outro destino | Outro (`1001\|198.51.0.20`) |
| Mesmo país, probes diferentes | Outro. O caminho e o ASN podem mudar. |

---

## 3. Rede do projeto

Não há rede física nova e não há `POST /measurements/`.

A overlay é o recorte dos pares que o grupo guarda, em cima do mesh que já pinga.

```text
Anchors do RIPE  --ping IPv4 a cada 240 s-->  pares escolhidos
        →  data/raw  →  Período A (baseline)  →  Período B (dataset)
```

| | Medição própria | Overlay |
|---|---|---|
| Chamada | `POST /measurements/` | `GET` no mesh |
| Quem pinga | A sonda de quem pediu | Anchors, o tempo todo |
| Custo | Créditos e chave | Zero |
| Série | Começa no pedido | Histórico já existente |
| O que entra no RTT | O último quilômetro de quem coletou | Caminho entre datacenters |
| O que se escolhe | Alvo, pacotes, intervalo | Quais pares e quais dias |

---

## 4. Primitivas

O projeto usa ping IPv4 (`af=4`). Rajada de cerca de 3 pacotes a cada 240 s. IPv6 (`af=6`) fica fora da mesma coluna de latência.

| Tipo | Mede | Neste projeto |
|---|---|---|
| **ping** | RTT, enviados, recebidos | Usado |
| **traceroute** | Salto a salto | Fora: não traz a rajada nem a perda |
| **dns** | Resolvedor | Fora: mistura DNS e caminho |
| **sslcert** | Certificado TLS | Fora: atraso de aplicação |
| **http** | Página | Fora: servidor + TLS + caminho |
| **ntp** | Relógio | Fora: não é degradação de enlace |

---

## 5. Origem, destino e topologia

Origem e destino são as duas pontas. Não são dois IPs avulsos.

| Ponta | Quem | Chave do fluxo |
|---|---|---|
| Origem | Anchor que envia | `prb_id` |
| Destino | Anchor que recebe | `dst_addr` |

Até 4 probes por país de origem. 1 a 3 IPs por destino. Cada probe × IP é um fluxo. O probe do próprio alvo fica de fora (auto-ping).

```text
probe 1001  →  200.0.0.10 (BR)     fluxo 1001|200.0.0.10
probe 1002  →  200.0.0.10 (BR)     fluxo 1002|200.0.0.10
probe 1001  →  203.0.113.8 (JP)    fluxo 1001|203.0.113.8
```

Setas = Anchors de um país pingam alvos de outro, a cada 240 s, IPv4.

```text
BR → BR, UY, BO, JP, IN, ZA
DE → DE, PT
AR → AR
ES → PL
ZA → KE
IN → SG
```

Coleta de referência: 12 rotas de país, 22 probes, 21 IPs, 67 fluxos. A rota de país é o desenho. Baseline e classe são por fluxo.

| Escopo | Pares | Papel |
|---|---|---|
| Curto | DE→DE, AR→AR, BR→BR | Normal baixo (ordem de 10–50 ms) |
| Regional | BR→UY, DE→PT, ES→PL, ZA→KE, IN→SG, BR→BO | Normal intermediário |
| Longo | BR→JP, BR→IN, BR→ZA | Normal alto (ordem de 300 ms) pode ser saudável |

`referencia_regional`, `regional_distante`, `intercontinental` e `rota_longa` nomeiam o escopo. Não são classe.

A diversidade coloca no mesmo arquivo um normal de ~10 ms e um normal de ~300 ms. A origem é escolhida por país. Probe sorteado no mesh mundial até um alvo no Brasil pode estar na Europa, e o RTT já nasce intercontinental.

---

## 6. Parâmetros

| Parâmetro | Valor | Motivo |
|---|---|---|
| `DIAS_PERIODO_A` | 7 | Estima o normal. Uma semana. |
| `DIAS_PERIODO_B` | 7, em seguida | Dataset. Não entra na mediana. |
| `BLOCO_DIAS` | 1 | Um dia por pedido. Cabe no timeout e permite retomar. |
| `NUM_PROBES_POR_PAR` | 4 | Caminhos diferentes. 5 ou mais deu timeout neste mesh. |
| Intervalo | 240 s | Do mesh. ~360 amostras por fluxo por dia. |
| Família | IPv4 | Um regime de RTT. |
| Tipo | `ping` | Rajada com RTT e perda. |
| Autenticação | nenhuma | `GET` público. |
| Timeout HTTP | 120 s, 3 tentativas | 429 e 5xx passam. |
| `probe_ids` | os probes escolhidos | Limita o download. |
| Cota de falha por rota | não há | Rota longa não é usada para encher FALHA. |

```text
360 amostras/dia × 7 = 2.520 no Período A
360 × 14 = 5.040 no fluxo (A+B), antes de tirar RTT inválido
```

Referência A+B: 336.326 registros, 06/09/2026 04:32 UTC a 20/09/2026 04:32 UTC. Total daquele recorte, não piso.

---

## 7. Baseline e as duas checagens

```text
Período A (7 dias)               Período B (7 dias)
mediana, MAD, jitter típico,     métricas relativas; classe na Tarefa 2
perda típica
B não entra na ficha
métrica em t usa só o mesmo fluxo com instante ≤ t
```

| | Checagem 1 | Checagem 2 |
|---|---|---|
| Teste | Fluxos que já estão no treino | Fluxos que não estão no treino |
| O que muda | O tempo (início de B treina, meio valida, fim testa) | O caminho |
| Baseline | Ficha do Período A | Período inicial desse fluxo, anterior ao trecho avaliado |
| Pergunta | A árvore vê degradação futura num fluxo conhecido? | A árvore vê degradação num caminho novo? |

Na checagem 2, o fluxo novo precisa da própria ficha e do piso de 1.500 RTT válidos. Sem a ficha, não há teste.

---

## 8. Métricas da amostra

| Campo | Conta | Sem resposta |
|---|---|---|
| `latencia_ms` | `avg` | vazio, nunca 0 |
| `perda_pct` | `(sent − rcvd) / sent × 100` | 100 |
| `jitter_ms` | desvio-padrão de `result[].rtt` | vazio com 0 ou 1 resposta; nunca 0 |
| `timeout_atual` | 1 se não há RTT ou perda = 100 | 1 |
| `probe_id` | `prb_id` | — |
| `fluxo_id` | `probe_id\|dst_addr` | — |
| `timestamp` | epoch UTC | — |

Sem `sent`, a linha sai. Perda 100% fica.

```text
latencia_relativa = latencia_atual / mediana_A
aumento_pct       = (latencia_atual − mediana_A) / mediana_A × 100
z_robusto         = (latencia_atual − mediana_A) / (1,4826 × MAD_A)
jitter_relativo   = jitter_atual / jitter_tipico_A
```

`MAD` = mediana de |RTT − mediana| no Período A, só com RTT presente. `MAD` = 0 e latência = mediana → `z_robusto` = 0. `MAD` = 0 e latência diferente → denominador = max(IQR / 1,349, 1 ms).

Conta, sem classe. Ficha imaginária: mediana 50 ms, MAD 2 ms.

```text
avg = 51 ms     →  z_robusto ≈ 0,3
rcvd = 0        →  latência vazia, perda = 100, timeout_atual = 1
```

---

## 9. Quantidade

Piso por fluxo, não pelo arquivo.

| Uso | Quantidade |
|---|---|
| Baseline | **1.500 RTT válidos** no Período A. Abaixo: `baseline_insuficiente`. Sem mediana inventada. |
| 7 dias a 240 s | ~2.520 amostras por fluxo, antes de tirar inválidos. |
| Referência | 3 de 67 fluxos ficaram abaixo do piso. A+B = 336.326 linhas. |

O fluxo novo da checagem 2 obedece ao mesmo piso de 1.500 no período inicial dele.
