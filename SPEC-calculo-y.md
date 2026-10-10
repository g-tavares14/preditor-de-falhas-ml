# Spec: Cálculo do Y (rótulo OK / RISCO / FALHA)

Status: **aprovada pelo dono em 01/10/2026**.

## Objetivo

Rotular cada medição do Período B com a regra da RFC §8.4 e entregar, na camada Gold, o dataset que a árvore vai
ler. Fecha a Tarefa 2 (`docs/projeto_preditor_redes/tarefas/Tarefa2_Baseline_e_Rotulagem.md`, seções 4 e 5).

A tabela nova tem as features que já existem mais quatro colunas:

| Coluna | Valores | O que é |
|---|---|---|
| `regra` | 1 a 6 | Qual linha da tabela da RFC §8.4 disparou (para auditoria) |
| `status_atual` | `OK`, `RISCO`, `FALHA` | Rótulo da medição (alvo do detector) |
| `status_futuro` | `OK`, `RISCO`, `FALHA` ou nulo | Rótulo do mesmo fluxo 12 minutos depois (alvo do preditor, RFC §3) |
| `bloco` | `treino`, `validacao`, `teste` | Recorte temporal dentro do Período B (Tarefa 2, seção 5) |

### Regra do `status_atual` (RFC §8.4: parar na primeira linha verdadeira)

| `regra` | Classe | Condição | Coluna que já existe em `features_B` |
|---|---|---|---|
| 1 | FALHA | `perda_pct` ≥ 10 | `perda_pct` |
| 2 | FALHA | `n5_timeout` ≥ 3 | `n5_timeout` |
| 3 | FALHA | `z_robusto` ≥ 3,5 (com RTT presente) | `z_robusto` (nulo sem RTT) |
| 4 | FALHA | `n5_aumento80` ≥ 2 | `n5_aumento80` |
| 5 | RISCO | desvio moderado nesta medição **e** `n5_risco` ≥ 2 | `moderado` e `n5_moderado` |
| 6 | OK | nenhuma das anteriores | — |

O "desvio moderado" da linha 5 (`2 ≤ z < 3,5`, ou `30 ≤ aumento_pct ≤ 80`, ou `jitter_relativo ≥ 3`) já é a coluna
`moderado`, e o `n5_risco` da RFC é a coluna `n5_moderado`. O cálculo do Y não recalcula nenhuma métrica: só lê as
colunas do X e aplica a tabela.

Recebem rótulo só as medições do Período B de fluxos com baseline (as linhas de `features_B`). O Período A e os
fluxos `baseline_insuficiente` não são rotulados.

### `status_futuro`

É o `status_atual` da 3ª medição seguinte do mesmo fluxo (3 intervalos de 240 s = 12 min). Fica **nulo** quando:

- não existem 3 medições à frente (as 3 últimas de cada fluxo);
- a 3ª medição à frente está a menos de 10 min ou a mais de 14 min (houve lacuna na coleta; o rótulo não seria "12
  minutos depois").

Linhas com `status_futuro` nulo continuam no dataset: servem ao detector, e o treino do preditor as descarta.

### `bloco`

Dois instantes de corte, iguais para todos os fluxos, a 50 % e a 70 % do intervalo entre o menor e o maior `t` do dataset rotulado (neste dataset, igual à duração do Período B):
`treino` = antes do primeiro corte, `validacao` = entre os dois, `teste` = depois do segundo. Sem sorteio de linhas.
Os instantes e o N de cada bloco por classe são impressos e gravados em CSV.

### Pré-requisito: medições duplicadas no Silver

O Período B tem **54 linhas duplicadas** (mesmo `fluxo_id`, mesmo `t`, mesmos valores; 40 pares/trios em 9 fluxos).
Hoje elas contam duas vezes na janela das "últimas 5" e deixariam "a 3ª medição à frente" ambígua. Esta spec remove
as duplicatas no Silver (uma linha por `fluxo_id` + `t`), **o que muda os números atuais**: o Silver, o baseline e
`features_B` passam a ter menos linhas e algumas contagens de janela mudam. A Tarefa 2 (seção 1) pede a auditoria
de duplicatas.

### Prévia (medida no Gold atual, ainda com as duplicatas)

| Classe | Linhas | Regra que disparou |
|---|---|---|
| FALHA | 18.307 (26 %) | perda: 1.381 · timeouts: 10 · `z` ≥ 3,5: 16.319 · aumento > 80 %: 597 |
| RISCO | 9.507 (13 %) | linha 5 |
| OK | 42.856 (61 %) | linha 6 |

Com o corte 50 / 20 / 30 os três blocos têm as três classes (RISCO: 5.153 / 1.685 / 2.669). Os números finais mudam
um pouco depois da remoção das duplicatas.

### Fora do escopo

- Treinar a árvore, escolher colunas do modelo, métricas de avaliação.
- O estado RECALIBRAR (RFC §8.5, pergunta em aberto nº 1 da RFC) e o `status_absoluto`.
- Mudar fórmulas ou limiares do X. A janela das "últimas 5" continua começando no início do Período B.
- Aplicar a folga entre blocos (RFC §9): as 3 últimas medições de um bloco têm `status_futuro` vindo do bloco
  seguinte. O dataset não as remove; quem treina o preditor decide (spec da árvore).
- Preencher o diário da Tarefa 2 e o dicionário v0.2.

## Stack

Sem mudança: Python + `uv`, PySpark 3.5 local. Nenhuma dependência nova.

## Comandos

```bash
uv run python -m preditor silver   # passa a remover duplicatas
uv run python -m preditor gold     # passa a gravar também o dataset rotulado
uv run python -m preditor          # bronze → silver → gold (precisa de rede)
```

## Estrutura do projeto

```
src/preditor/
  config.py                      → 4 limiares do rótulo, horizonte do futuro, proporções do recorte, caminhos novos
  silver/medicao.py              → remoção de duplicatas (fluxo_id + t)
  gold/calculo_y/rotulo.py       → classe Rotulo: regra, status_atual, status_futuro
  gold/calculo_y/recorte.py      → classe Recorte: coluna bloco
  __main__.py                    → executar_gold grava e verifica as saídas novas
data/gold/
  dataset_rotulado_B.parquet     → features + regra + status_atual + status_futuro + bloco
  contagem_classes.csv           → bloco × classe, com os instantes de corte (leitura humana)
```

`features_B.parquet`, `baseline_por_fluxo.parquet` e `limites_por_regiao.csv` continuam sendo gravados.

## Estilo de código

Segue o `AGENTS.md`. A regra é escrita na mesma ordem da tabela da RFC, uma linha por linha da tabela:

```python
# RFC §8.4: a primeira condição verdadeira decide. Comparação com nulo dá nulo,
# e o when() trata nulo como falso: sem RTT, as linhas de z não disparam.
regra = (
    F.when(F.col("perda_pct") >= config.PERDA_FALHA_PCT, 1)
    .when(F.col("n5_timeout") >= config.N5_TIMEOUT_FALHA, 2)
    .when(F.col("z_robusto") >= config.Z_FALHA, 3)
    .when(F.col("n5_aumento80") >= config.N5_AUMENTO80_FALHA, 4)
    .when((F.col("moderado") == 1) & (F.col("n5_moderado") >= config.N5_RISCO), 5)
    .otherwise(6)
)
```

Constantes novas em `config.py`, com a origem: `PERDA_FALHA_PCT = 10`, `N5_TIMEOUT_FALHA = 3`,
`N5_AUMENTO80_FALHA = 2`, `N5_RISCO = 2` (RFC §8.4); `PASSOS_FUTURO = 3`, `FUTURO_MIN_S = 600`, `FUTURO_MAX_S = 840`
(RFC §3 + decisão desta spec); `FRACAO_TREINO = 0.5`, `FRACAO_VALIDACAO = 0.2` (Tarefa 2, seção 5).

## Estratégia de testes

Sem framework de testes. A verificação é o pipeline, com checagens automáticas novas:

- Silver: nenhum par (`fluxo_id`, `t`) repetido.
- Gold, dataset rotulado:
  - mesmo número de linhas de `features_B`; `status_atual` e `bloco` nunca nulos e só com os valores previstos;
  - coerência regra ↔ classe (1 a 4 = FALHA, 5 = RISCO, 6 = OK);
  - precedência: toda linha com `perda_pct` ≥ 10 é FALHA; nenhuma linha OK tem `z_robusto` ≥ 3,5;
  - `status_futuro` não nulo implica que a 3ª medição à frente existe, está entre 10 e 14 min e tem aquele rótulo;
  - `bloco` respeita o tempo (todo `treino` antes de toda `validacao`, antes de todo `teste`);
  - os três blocos têm as três classes (senão o programa para e pede ajuste das proporções).
- Impressão: contagem por classe e por regra, nulos de `status_futuro`, instantes de corte e N por bloco.

As contagens por classe **não** viram número fixo em `config.py`: são resultado, não parâmetro.

## Limites

- **Sempre:** aplicar a tabela da RFC na ordem; limiares em `config.py` com a origem; rótulo só no Período B e só
  para fluxos com baseline; atualizar `AGENTS.md` e `README.md`.
- **Perguntar antes:** mudar qualquer limiar ou fórmula; mudar o X além do efeito da remoção de duplicatas;
  adicionar dependências; descartar linhas do dataset rotulado.
- **Nunca:** usar região, país, IP, `fluxo_id` ou RTT absoluto para decidir a classe; rotular o Período A; preencher
  RTT ausente com 0; commitar dados.

## Critérios de sucesso

- [x] O Silver não tem nenhum par (`fluxo_id`, `t`) repetido; o número de duplicatas removidas é impresso.
- [x] `FLUXOS_SILVER`, `FLUXOS_BASELINE` e `FLUXOS_INSUFICIENTES` continuam valendo (82 / 81 / 2) depois da remoção;
      se algum mudar, a implementação para e pergunta.
- [x] `uv run python -m preditor gold` grava `dataset_rotulado_B.parquet` com as colunas de `features_B` mais
      `regra`, `status_atual`, `status_futuro`, `bloco`, e passa em todas as checagens acima.
- [x] `contagem_classes.csv` mostra bloco × classe e os dois instantes de corte.
- [x] Os três blocos têm OK, RISCO e FALHA.
- [x] Três exemplos reais são impressos para o diário: um OK de caminho longo (RTT alto, `z` baixo), um RISCO e um
      FALHA, cada um com as métricas e a `regra` que disparou.
- [x] `AGENTS.md` (estágio atual, decisões) e `README.md` (saídas do Gold) descrevem o Y.

## Decisões fechadas (01/10/2026)

1. **Duplicatas:** removidas no Silver (uma linha por `fluxo_id` + `t`), aceitando que `features_B` e o baseline
   mudam em relação ao commit `f1e36b0`.
2. **Recorte por instante global:** dois instantes de corte iguais para todos os fluxos, a 50 % e 70 % da duração
   do Período B.
3. **Tolerância do `status_futuro`:** 10 a 14 min; fora disso, nulo.
4. **Limiares da RFC mantidos**, mesmo com FALHA em cerca de 26 % das linhas.
5. **Regra do `z_robusto` (Checkpoint A, 01/10/2026, revista em 09/10/2026):** primeiro sem piso, com a linha 3 da RFC
   ao pé da letra. Naquele rótulo, das 16.305 FALHAs dessa regra, 88 % tinham `aumento_pct` abaixo de 30 % (fluxos muito
   estáveis, com MAD pequeno). Desde 10/10/2026 a linha 3 exige também `aumento_pct` ≥ 30 % (`PISO_AUMENTO_FALHA_PCT`;
   `None` = a RFC ao pé da letra). Motivo, medidas e ressalvas: `SPEC-piso-regra3.md` e a seção 8 do relatório.
