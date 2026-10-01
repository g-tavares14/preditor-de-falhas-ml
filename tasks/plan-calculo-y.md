# Plano de implementação: cálculo do Y

Spec: [`SPEC-calculo-y.md`](../SPEC-calculo-y.md) (aprovada em 01/10/2026). Tarefas detalhadas em
[`todo-calculo-y.md`](todo-calculo-y.md). O plano anterior (medalhão) continua em `plan.md` / `todo.md`.

## Visão geral

O Gold ganha uma tabela nova, `dataset_rotulado_B.parquet`: as features que já existem mais `regra`,
`status_atual`, `status_futuro` e `bloco`. Antes disso, o Silver passa a remover medições duplicadas, porque elas
distorcem a janela das "últimas 5" e deixam "a 3ª medição à frente" ambígua. Cada tarefa acrescenta uma coluna e
suas checagens, e o pipeline continua rodando ao fim de cada uma. Tudo roda offline (`silver` e `gold`).

## Decisões de arquitetura

- **Duplicatas primeiro (Y1).** É a única tarefa que muda números já publicados (Silver, baseline, `features_B`).
  Fica isolada para que a diferença antes/depois seja medida e mostrada ao dono antes de qualquer rótulo.
- **Remoção só de linhas idênticas.** `dropDuplicates()` na linha inteira do Silver. Se sobrar algum par
  (`fluxo_id`, `t`) com valores diferentes, não há critério para escolher: a implementação para e pergunta.
- **O Y não recalcula métricas.** `Rotulo` lê as colunas de `features_B` (`perda_pct`, `n5_timeout`, `z_robusto`,
  `n5_aumento80`, `moderado`, `n5_moderado`) e aplica a tabela da RFC §8.4 com um `when` encadeado, na ordem.
- **`regra` antes de `status_atual`.** A classe é derivada da regra (1 a 4 = FALHA, 5 = RISCO, 6 = OK), o que torna
  a coerência entre as duas garantida por construção e auditável.
- **`status_futuro` com `lead(3)` por fluxo**, mais a diferença de tempo até essa linha; fora de 600 a 840 s vira
  nulo. Sem duplicatas, a ordem por `t` dentro do fluxo é única.
- **`bloco` por instante global.** Os dois cortes saem do mínimo e do máximo de `t` do dataset rotulado e são
  calculados dentro do Spark (como o corte A/B), para não sofrer conversão de fuso.
- **Uma tabela, não quatro.** `features_B.parquet` continua sendo gravado como hoje; o dataset rotulado é gravado à
  parte, e as checagens rodam sobre o arquivo relido do disco.
- **Contagens por classe não viram constante.** São impressas e gravadas em `contagem_classes.csv`.

## Ordem e dependências

```
Y1 duplicatas no Silver
 └─ Y2 regra + status_atual        ← checkpoint A (dono vê a distribuição)
     └─ Y3 status_futuro
         └─ Y4 bloco + contagem_classes.csv
             └─ Y5 exemplos auditáveis + documentação
```

Sequencial: cada coluna depende da anterior e todas passam por `__main__.py` e `config.py`.

## Lista de tarefas

### Fase 1: base
- [x] Y1: Remover medições duplicadas no Silver
- [x] Y2: `regra` e `status_atual` no Gold

### Checkpoint A (revisão do dono)
- [ ] Diferença antes/depois das duplicatas e distribuição das classes conferidas

### Fase 2: alvo futuro e recorte
- [x] Y3: `status_futuro`
- [x] Y4: `bloco` e `contagem_classes.csv`

### Fase 3: acabamento
- [x] Y5: Exemplos auditáveis e documentação

### Checkpoint final
- [ ] Todos os critérios de sucesso da spec marcados

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Duplicatas com valores diferentes no mesmo (`fluxo_id`, `t`) | Alto | Y1 conta os dois tipos antes de remover; se houver não idênticas, para e pergunta |
| A remoção mudar 82 / 81 / 2 fluxos ou tirar um fluxo do piso de 1.500 | Alto | As checagens existentes continuam; se falharem, Y1 para e relata |
| A remoção deslocar o corte A/B | Médio | Y1 compara o corte impresso com `2026-09-22 14:10:03` |
| Nulos na regra (sem RTT, `z_robusto` nulo) caírem na classe errada | Alto | `when` trata nulo como falso; checagens de precedência em Y2; os 190 timeouts do Período B têm perda 100 % e caem na linha 1 |
| Um bloco ficar sem RISCO depois da remoção | Médio | Checagem em Y4 para o programa; a prévia mostrou as 3 classes nos 3 blocos |
| Distribuição final muito diferente da prévia (61 / 13 / 26 %) | Médio | Y2 relata a distribuição; checkpoint A antes de seguir |

## Questões em aberto

Nenhuma. Skills do catálogo: nenhuma tarefa pede uma que não esteja instalada.
