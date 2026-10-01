# Tarefas: cálculo do Y

Plano: [`plan-calculo-y.md`](plan-calculo-y.md) · Spec: [`SPEC-calculo-y.md`](../SPEC-calculo-y.md)

Verificação padrão de toda tarefa (o projeto não tem testes nem linter): `uv run python -c "import preditor.__main__"`,
`uv run python -m preditor silver` e `uv run python -m preditor gold` (os dois rodam offline, a partir do Bronze que já
está no disco).

---

## ✅ Y1: Remover medições duplicadas no Silver

**Descrição:** Antes de mudar o código, anotar os números atuais (linhas do Silver, linhas de `features_B`, corte
A/B). Em `silver/medicao.py`, remover linhas totalmente idênticas ao fim de `transformar()`. Adicionar a checagem
"nenhum par (`fluxo_id`, `t`) repetido" em `_verificar_silver` e imprimir quantas duplicatas saíram.

**Critérios de aceite:**
- [ ] Contagem de duplicatas antes da remoção, por período (A e B), separando idênticas de não idênticas
- [ ] Se houver par (`fluxo_id`, `t`) com valores diferentes: parar e perguntar ao dono (não escolher uma linha)
- [ ] Silver sem pares (`fluxo_id`, `t`) repetidos; checagem automática
- [ ] 82 / 81 / 2 fluxos e o corte A/B `2026-09-22 14:10:03` continuam valendo; senão, parar e relatar
- [ ] Números antes/depois anotados em "Números de referência" no fim deste arquivo: linhas do Silver, linhas de
      `features_B`, e quantos fluxos tiveram mediana ou MAD do baseline alterados

**Verificação:**
- [ ] `uv run python -m preditor silver` e `uv run python -m preditor gold`

**Dependências:** nenhuma
**Arquivos:** `src/preditor/silver/medicao.py`, `src/preditor/__main__.py`, `tasks/todo-calculo-y.md`
**Escopo:** pequeno

## ✅ Y2: `regra` e `status_atual` no Gold

**Descrição:** Criar `gold/calculo_y/rotulo.py` com a classe `Rotulo`, que recebe `features_B` e devolve o mesmo
DataFrame com `regra` (1 a 6, tabela da RFC §8.4 na ordem) e `status_atual`. Limiares novos em `config.py`.
`executar_gold` grava `dataset_rotulado_B.parquet` e roda as checagens sobre o arquivo relido.

**Critérios de aceite:**
- [ ] `config.py` tem `PERDA_FALHA_PCT`, `N5_TIMEOUT_FALHA`, `N5_AUMENTO80_FALHA`, `N5_RISCO` (origem: RFC §8.4) e
      `ARQUIVO_ROTULADO`
- [ ] `dataset_rotulado_B.parquet` tem as colunas de `features_B` mais `regra` e `status_atual`, com o mesmo número
      de linhas
- [ ] Checagens automáticas: `status_atual` nunca nulo e só OK / RISCO / FALHA; regra 1 a 4 = FALHA, 5 = RISCO,
      6 = OK; toda linha com `perda_pct` ≥ 10 é FALHA; nenhuma linha OK tem `z_robusto` ≥ 3,5
- [ ] O pipeline imprime a contagem por classe e por regra
- [ ] Nenhuma coluna de região, país, IP ou `fluxo_id` participa da regra
- [ ] `features_B.parquet` continua sendo gravado, sem as colunas novas

**Verificação:**
- [ ] `uv run python -m preditor gold`
- [ ] Prova de que uma checagem falha com dado errado (ex.: trocar um limiar só em memória)

**Dependências:** Y1
**Arquivos:** `src/preditor/gold/calculo_y/rotulo.py`, `src/preditor/gold/calculo_y/__init__.py`,
`src/preditor/config.py`, `src/preditor/__main__.py`
**Escopo:** médio

## Checkpoint A (revisão do dono)
- [ ] Diferença antes/depois da remoção de duplicatas conferida
- [ ] Distribuição OK / RISCO / FALHA conferida (prévia: 61 / 13 / 26 %)

---

## ✅ Y3: `status_futuro`

**Descrição:** Em `Rotulo`, adicionar `status_futuro`: o `status_atual` da 3ª medição seguinte do mesmo fluxo, nulo
quando ela não existe ou está fora de 600 a 840 s. Constantes em `config.py`.

**Critérios de aceite:**
- [ ] `config.py` tem `PASSOS_FUTURO = 3`, `FUTURO_MIN_S = 600`, `FUTURO_MAX_S = 840`, com a origem (RFC §3 e
      decisão da spec)
- [ ] `status_futuro` é nulo ou OK / RISCO / FALHA; as 3 últimas medições de cada fluxo têm nulo
- [ ] Checagem automática: para toda linha com `status_futuro` não nulo, a 3ª medição à frente do fluxo existe,
      está entre 600 e 840 s e tem aquele `status_atual` (conferida por um caminho independente do `lead`, por
      exemplo um join por posição na série)
- [ ] O pipeline imprime quantas linhas têm futuro nulo e por qual motivo (fim da série / lacuna)
- [ ] Nenhuma coluna auxiliar (posição, diferença de tempo) fica no dataset gravado

**Verificação:**
- [ ] `uv run python -m preditor gold`

**Dependências:** Y2
**Arquivos:** `src/preditor/gold/calculo_y/rotulo.py`, `src/preditor/config.py`, `src/preditor/__main__.py`
**Escopo:** pequeno

## ✅ Y4: `bloco` e `contagem_classes.csv`

**Descrição:** Criar `gold/calculo_y/recorte.py` com a classe `Recorte`, que adiciona `bloco` (treino / validacao /
teste) por dois instantes de corte globais, a 50 % e 70 % do intervalo entre o menor e o maior `t` do dataset
rotulado. Gravar `contagem_classes.csv` (bloco × classe, com os instantes de corte).

**Critérios de aceite:**
- [ ] `config.py` tem `FRACAO_TREINO = 0.5`, `FRACAO_VALIDACAO = 0.2` (origem: Tarefa 2, seção 5) e
      `ARQUIVO_CONTAGEM`
- [ ] `bloco` nunca nulo e só com os três valores
- [ ] Checagens automáticas: o maior `t` do treino é menor que o menor `t` da validação, e o mesmo entre validação
      e teste; os três blocos têm OK, RISCO e FALHA (senão o programa para)
- [ ] O pipeline imprime os dois instantes de corte e o N de cada bloco por classe
- [ ] `contagem_classes.csv` gravado em `docs/data/gold/`, legível por humano

**Verificação:**
- [ ] `uv run python -m preditor gold`

**Dependências:** Y3
**Arquivos:** `src/preditor/gold/calculo_y/recorte.py`, `src/preditor/config.py`, `src/preditor/__main__.py`
**Escopo:** pequeno

## ✅ Y5: Exemplos auditáveis e documentação

**Descrição:** O pipeline imprime três linhas reais para o diário da Tarefa 2: um OK de caminho longo (RTT alto,
`z_robusto` baixo), um RISCO e um FALHA, com as métricas e a `regra`. Atualizar `AGENTS.md` (estágio atual,
decisões: duplicatas, futuro, recorte) e `README.md` (saídas do Gold). Corrigir os comentários de `config.py` que
citam os números de referência. Marcar os critérios de sucesso da spec.

**Critérios de aceite:**
- [ ] Três exemplos impressos, escolhidos de forma determinística (mesma saída a cada execução)
- [ ] `AGENTS.md` não diz mais que o Y "ainda não foi implementado"; decisões novas registradas
- [ ] `README.md` lista `dataset_rotulado_B.parquet` e `contagem_classes.csv`
- [ ] Docstring de `gold/calculo_y/__init__.py` atualizado
- [ ] Critérios de sucesso de `SPEC-calculo-y.md` marcados

**Verificação:**
- [ ] `uv run python -m preditor gold` duas vezes: mesmos exemplos
- [ ] `grep -rn "não implementado\|ainda não foi implementado" AGENTS.md README.md src/` não retorna nada

**Dependências:** Y4
**Arquivos:** `src/preditor/__main__.py`, `src/preditor/gold/calculo_y/__init__.py`, `src/preditor/config.py`,
`AGENTS.md`, `README.md`, `SPEC-calculo-y.md`
**Escopo:** médio

## Checkpoint final
- [ ] Todos os critérios de sucesso de `SPEC-calculo-y.md` marcados
- [ ] Pronto para `/review`

---

## Números de referência

Medidos na Y1 (01/10/2026), sobre o Silver e o Gold gerados pelo código anterior (antes) e pelo código com
`dropDuplicates()` (depois). Dataset de 7 dias, Bronze com 199.025 linhas.

| Medida | Antes | Depois |
|---|---|---|
| Linhas do Silver | 199.025 | 198.962 (63 duplicatas removidas) |
| Fluxos no Silver / baseline / insuficientes | 82 / 81 / 2 | 82 / 81 / 2 |
| Corte A/B | `2026-09-22 14:10:03` | `2026-09-22 14:10:03` |
| Linhas de `features_B` | 70.670 | 70.616 (-54) |
| Grupos (`fluxo_id`, `t`) repetidos, Período A | 9 grupos, 9 linhas a mais, 9 fluxos | 0 |
| Grupos (`fluxo_id`, `t`) repetidos, Período B | 40 grupos, 54 linhas a mais, 9 fluxos | 0 |
| Grupos com valores diferentes (não idênticos) | 0 | 0 |

Todas as duplicatas eram linhas totalmente idênticas, então `dropDuplicates()` na linha inteira basta. As 9 do
Período A não estavam na medição prévia da spec (que olhou só o Período B): elas entram no cálculo do baseline.

Efeito no baseline (81 fluxos comparados com a cópia de `baseline_por_fluxo.parquet` de antes):

| Coluna | Fluxos alterados | Maior diferença absoluta |
|---|---|---|
| `mediana` | 9 | 0,0039 ms |
| `mad` | 9 | 0,0122 ms |

São os mesmos 9 fluxos com duplicata no Período A (também mudam `n_medicoes` e `n_validos`, em 1 cada). Nenhum
valor passou de nulo para não nulo nem o contrário, e nenhum fluxo mudou de `baseline_insuficiente`.
