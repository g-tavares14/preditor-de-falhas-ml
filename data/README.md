# Fonte dos dados

Esta pasta documenta os dados usados pelo projeto. A extração regional descrita aqui vem de medições públicas do RIPE Atlas consultadas no BigQuery.

## Origem da extração regional

- Fonte: RIPE Atlas BigQuery.
- Tabela consultada: `ripencc-atlas.measurements.ping`.
- Tipo de medição: ping IPv4 (`af = 4`).
- Janela: sete dias anteriores ao momento em que a consulta é executada.
- Filtro adicional: registros com `packets_sent > 0`.
- A consulta seleciona as linhas que correspondem aos `prb_id` e destinos listados abaixo. O resultado bruto é preparado e rotulado posteriormente em Python.

## Probes de origem (`prb_id`)

```text
6349, 6410, 6602, 6659, 6790, 6891, 6977,
7019, 7113, 7242, 7307, 7508, 7708
```

## Destinos selecionados

| Endereço IP | País | Região |
|---|---|---|
| `150.164.1.222` | BR | Brasil |
| `92.38.132.60` | US | América do Norte |
| `91.209.16.127` | PT | Europa |
| `129.143.66.65` | DE | Europa |
| `202.6.102.41` | SG | Ásia |
| `133.69.15.4` | JP | Ásia |

Os `prb_id` e os endereços de destino são registrados separadamente; esta lista não declara uma associação individual entre cada probe e cada destino.

## Documentos relacionados

- [Índice da documentação](../docs/README.md): visão geral das pastas e documentos em `../docs`.
- [História da exploração e consultas BigQuery](docs/query.md): como o recorte regional foi definido e as consultas SQL usadas.
- [Evolução da fonte de dados](dataset-fonte-atlas.md): por que o projeto passou da coleta própria para medições públicas do RIPE Atlas no BigQuery.
- [Guia de coleta RIPE Atlas da professora](../docs/projeto_preditor_redes/Guia_Coleta_RIPE_Atlas.md).
- [RFC do projeto acadêmico](../docs/projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md).

As orientações acadêmicas e os registros do grupo estão organizados em [`projeto_preditor_redes/`](../docs/projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md) e [`memorando/`](../docs/memorando/memorando_de_decisao_grupo16.md).
