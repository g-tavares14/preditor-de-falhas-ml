# Etapa 6: Coleta de medições (baseline, Período A)

**Status:** ✅ coleta concluída — 240 medições registradas no Período A, distribuídas em 12 fluxos (20 rajadas por fluxo). Baseline reduzida, com validação metodológica pendente. Planilha de coleta: [data/coleta_baseline.xlsx](../data/coleta_baseline.xlsx).

## Procedimento (ATA)

No Command Prompt de cada Probe, com a rede saudável, uma rajada de 3 pacotes: `ping -n 3 <IP do Alvo>`.
**Decisão de montagem:** 20 rajadas por fluxo (60 RTT) com a rede saudável, em vez do piso de 1.500 RTT do repositório.
Pela regra do repositório isso seria `baseline_insuficiente`; deixar a adaptação explícita no relatório.

## Como coletar

1. Ping de aquecimento no Probe (para o ARP não distorcer) e depois `ping -n 3 <IP do Alvo>`.
2. Na aba **Coleta** de `coleta_baseline.xlsx`, preencher timestamp (UTC) e `rtt1`, `rtt2`, `rtt3` da rajada.
   `<1ms` = `0.5`; pacote sem resposta = `T` (nunca 0).
3. A aba **Baseline** calcula a ficha de cada fluxo; a aba **medicoes_pt** é a que se exporta como CSV.

Fluxos (20 rajadas cada): Probe-BR → .10 (BR), .11 (UY), .12 (BO), 42.10 (JP), 40.10 (IN), 30.10 (ZA);
Probe-DE → 20.10 e 21.10; Probe-AR → 13.10; Probe-ES → 23.10; Probe-ZA → 31.10; Probe-IN → 41.10.

## Regras de preenchimento do CSV

- `<1ms` vira **0,5 ms**.
- `Request timed out` e `Destination host unreachable` = pacote não respondido; **latência vazia, nunca 0**.
- `latencia_ms` = média dos RTT válidos da rajada; `perda_pct` = (sent − rcvd) / sent × 100.
- `jitter_ms`: escolher **um** critério e usar em todo o CSV (README: média de |Δrtt|; Guia: desvio-padrão). **Critério escolhido: média de |Δrtt| entre pings consecutivos que responderam (README do repositório).** Vazio se não há dois pings consecutivos válidos.
- `jitter_ms` vazio com 0 ou 1 resposta; `timeout_atual` = 1 se não há RTT ou perda = 100.
- `fluxo_id` = `Probe-XX|IP do Alvo`; `timestamp` em UTC; `periodo` = A.

Arquivo: [`data/medicoes_pt.csv`](../data/medicoes_pt.csv).

## Ficha de baseline por fluxo (só Período A)

Calcular por fluxo: mediana, MAD, IQR, jitter típico, perda típica e taxa de resposta.
MAD = mediana de |RTT − mediana| usando só RTT presente.

| fluxo_id | mediana | MAD | IQR | jitter típico | perda típica | taxa de resposta |
|---|---|---|---|---|---|---|
| (preencher após a coleta) | | | | | | |

## Métricas relativas

```
latencia_relativa = latencia_atual / mediana_A
aumento_pct       = (latencia_atual - mediana_A) / mediana_A * 100
z_robusto         = (latencia_atual - mediana_A) / (1,4826 * MAD_A)
```

Se MAD = 0 e a latência é igual à mediana, `z_robusto` = 0. Se MAD = 0 e a latência é diferente, o denominador vira `max(IQR / 1,349, 1 ms)`.

## Resultados da coleta do Período A

A coleta do Período A foi concluída no Cisco Packet Tracer.

- Total de medições: 240
- Quantidade de fluxos: 12
- Medições por fluxo: 20
- Objetivo: estabelecer uma referência de latência e jitter para cada rota.

Os dados foram utilizados pelo arquivo `classificar_medicoes.py`
para calcular a mediana, o MAD e o jitter típico de cada fluxo.

A baseline foi utilizada na classificação preliminar das
80 medições do Período B.

**Limitação:** foram utilizadas 20 rajadas de três pings
por fluxo, quantidade inferior ao mínimo de 1.500 RTTs
válidos exigido pelo projeto original. Portanto, a baseline
é uma adaptação experimental e ainda precisa de validação.