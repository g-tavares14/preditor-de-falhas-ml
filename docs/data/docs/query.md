# Consultas BigQuery

Este documento registra como o recorte regional de medições ICMP foi construído e guarda as consultas usadas na exploração e na extração. A fonte continua sendo o RIPE Atlas; o BigQuery permite consultar medições públicas já existentes sem depender de novos créditos para criar medições.

## Como chegamos ao recorte atual

### 1. Partimos da pergunta: quais probes brasileiras produziam medições úteis?

A exploração começou pela lista de probes públicas do RIPE Atlas no Brasil. A lista inicial tinha 433 probes, mas esse número não significava que todas estivessem conectadas ou produzindo medições. Por isso, a seleção do estudo foi direcionada às probes brasileiras que apareciam associadas a resultados de ping no histórico consultado, em vez de usar indiscriminadamente todas as probes da lista.

O recorte levado para a consulta regional contém 13 `prb_id`: `6349`, `6410`, `6602`, `6659`, `6790`, `6891`, `6977`, `7019`, `7113`, `7242`, `7307`, `7508` e `7708`.

### 2. Em seguida, observamos os destinos registrados nas medições

Na tabela `ripencc-atlas.measurements.ping`, os campos `prb_id` e `dst_addr` permitem observar qual probe aparece em cada medição e qual endereço recebeu o ping. A consulta exploratória inicial trouxe esses campos junto com horário e contagens de pacotes. Essa amostra ajudou a entender a estrutura dos registros e a procurar endereços de destino conhecidos.

O resultado exportado também foi usado para investigar quais destinos apareciam nas medições. A consulta regional final restringe a extração aos 13 IDs escolhidos e a endereços de destino selecionados. Assim, ela retorna apenas combinações probe-destino que realmente têm registros na tabela: não cria uma combinação para cada probe e cada destino, nem garante que todas as probes tenham consultado todos os destinos.

### 3. Escolhemos âncoras para comparar rotas por região

A ideia do projeto passou a ser comparar medições originadas no Brasil para destinos locais e intercontinentais. Os endereços selecionados foram organizados em quatro grupos de rota:

| Grupo | Destino-âncora | País | Motivo no estudo |
|---|---|---|---|
| `BR → BR` | `150.164.1.222` | Brasil | Referência de rota nacional. |
| `BR → América do Norte` | `92.38.132.60` | EUA | Âncora identificada em Miami. |
| `BR → Europa` | `91.209.16.127` | Portugal | Um destino europeu. |
| `BR → Europa` | `129.143.66.65` | Alemanha | Segundo destino europeu para ampliar a comparação na região. |
| `BR → Ásia` | `202.6.102.41` | Singapura | Um destino asiático. |
| `BR → Ásia` | `133.69.15.4` | Japão | Segundo destino asiático para ampliar a comparação na região. |

A escolha busca representar distâncias e regiões diferentes. A mesma latência pode ter interpretações distintas em uma rota nacional e em uma rota intercontinental; por isso, os destinos recebem metadados de país e região para permitir a análise por grupo. Esses metadados são associados aos endereços na consulta, não inferidos automaticamente pelo BigQuery.

### 4. Ampliamos a janela para sete dias e fixamos a extração

A primeira consulta usava uma janela de um dia e um limite de 20 linhas, adequado para uma inspeção rápida, mas pequeno para formar o recorte do estudo. A consulta final considera os sete dias anteriores à execução, filtra IPv4 (`af = 4`), exige `packets_sent > 0` e mantém somente os IDs e destinos selecionados.

A consulta retorna medições brutas. A preparação das métricas e a criação do rótulo `status_real` continuam no Python, conforme o contrato do dataset do projeto. O recorte de sete dias também não comprova que uma probe esteja conectada neste instante: ele indica apenas que há registros no período consultado.

## Consulta exploratória — últimas 24 horas

Amostra inicial da tabela para inspecionar as medições de ping, os IDs das probes, os endereços de destino e as contagens de pacotes. A perda calculada aqui é um campo auxiliar para exploração; o limite de 20 linhas não representa uma extração completa nem permite, sozinho, concluir quais probes brasileiras estão ativas.

```sql
SELECT
  start_time,
  prb_id,
  dst_addr,
  packets_sent,
  packets_received,
  ROUND(
    SAFE_DIVIDE(packets_sent - packets_received, packets_sent) * 100,
    2
  ) AS loss_pct
FROM `ripencc-atlas.measurements.ping`
WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND packets_sent > 0
LIMIT 20;
```

## Consulta regional — últimos 7 dias

Extrai as medições observadas para as 13 probes e os seis destinos-âncora descritos acima. O `JOIN` por `dst_addr` acrescenta país e região às linhas que correspondem aos endereços selecionados.

```sql
WITH source_probe_ids AS (
  SELECT probe_id
  FROM UNNEST([
    6349, 6410, 6602, 6659, 6790, 6891, 6977,
    7019, 7113, 7242, 7307, 7508, 7708
  ]) AS probe_id
),
selected_destinations AS (
  SELECT *
  FROM UNNEST([
    STRUCT('150.164.1.222' AS dst_addr, 'BR' AS destination_country, 'Brasil' AS destination_region),
    STRUCT('92.38.132.60' AS dst_addr, 'US' AS destination_country, 'América do Norte' AS destination_region),
    STRUCT('91.209.16.127' AS dst_addr, 'PT' AS destination_country, 'Europa' AS destination_region),
    STRUCT('129.143.66.65' AS dst_addr, 'DE' AS destination_country, 'Europa' AS destination_region),
    STRUCT('202.6.102.41' AS dst_addr, 'SG' AS destination_country, 'Ásia' AS destination_region),
    STRUCT('133.69.15.4' AS dst_addr, 'JP' AS destination_country, 'Ásia' AS destination_region)
  ])
)
SELECT
  m.start_time,
  m.msm_id,
  m.group_id,
  m.prb_id,
  m.af,
  m.src_addr,
  m.dst_addr,
  d.destination_country,
  d.destination_region,
  m.size,
  m.packets_sent,
  m.packets_received,
  m.last_time_synced,
  m.pings
FROM `ripencc-atlas.measurements.ping` AS m
JOIN source_probe_ids AS s
  ON m.prb_id = s.probe_id
JOIN selected_destinations AS d
  ON m.dst_addr = d.dst_addr
WHERE m.start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND m.start_time < CURRENT_TIMESTAMP()
  AND m.af = 4
  AND m.packets_sent > 0
ORDER BY
  m.start_time,
  d.destination_region,
  d.destination_country,
  m.prb_id;
```
