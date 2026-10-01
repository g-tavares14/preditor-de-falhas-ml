# Plano de implementação: árvore inicial (Tarefa 3)

Spec: [`SPEC-arvore.md`](../SPEC-arvore.md) (aprovada em 01/10/2026). Tarefas detalhadas em
[`todo-arvore.md`](todo-arvore.md). Os planos anteriores continuam em `plan.md` / `todo.md` (medalhão) e
`plan-calculo-y.md` / `todo-calculo-y.md` (Y).

## Visão geral

O projeto ganha o comando `uv run python -m preditor arvore`, que lê o Gold do disco e treina a primeira árvore de
decisão: alvo `status_futuro` (12 min à frente), 8 colunas relativas ao baseline, scikit-learn, sem balanceamento de
classes. A árvore é medida na validação ao lado da persistência ("o futuro é igual ao `status_atual`") e comparada
com uma árvore de contraste que enxerga `rtt` e `destination_region`. Cada tarefa deixa o comando rodando, com
checagens automáticas. Prazo do diário da Tarefa 3: 04/10/2026.

## Decisões de arquitetura

- **Pasta nova `src/preditor/modelo/`**, fora do medalhão: `dados.py` (`DadosModelo`), `arvore.py` (`Arvore`),
  `avaliacao.py` (`Avaliacao`) e `execucao.py` (`ExecucaoArvore`: orquestra, grava e verifica). `__main__.py` só
  ganha a opção `arvore` e chama `ExecucaoArvore().executar()`: ele já tem 430 linhas só de Spark.
- **`arvore` não sobe o Spark.** Em `main()`, o desvio para `arvore` vem antes de `build_spark`: roda sem Java.
  Sem o Gold no disco, termina com `SystemExit` no mesmo formato de `Pipeline._ler_camada`.
- **Leitura com pandas + pyarrow** de `config.ARQUIVO_ROTULADO` e `config.ARQUIVO_BASELINE` (mediana do fluxo, só
  para classificar caminho longo / curto nos erros concretos).
- **Folga antes do filtro de nulos.** As 3 últimas medições de cada (`fluxo_id`, `bloco`) são marcadas no dataset
  inteiro, ordenado por `t`; só depois saem as linhas com `status_futuro` nulo. Na ordem inversa, as "3 últimas"
  seriam outras linhas e o futuro do bloco seguinte vazaria.
- **Nulo fica nulo.** X vira `float64` com `NaN`; o `DecisionTreeClassifier` (scikit-learn ≥ 1.4) trata `NaN` na
  divisão. Nenhum `fillna`.
- **Persistência primeiro (A2).** A régua de comparação é medida antes de existir árvore: o dono vê o número a
  bater antes de qualquer escolha de hiperparâmetro.
- **Uma só função de métricas** (`Avaliacao.medir(verdadeiro, previsto)`) serve à persistência, à árvore oficial e
  à de contraste, sempre na ordem `CLASSES = ("OK", "RISCO", "FALHA")`. Ela recusa linhas do bloco `teste`.
- **Escolha determinística na grade:** maior F1 macro na validação; empate → menor `max_depth`, depois maior
  `min_samples_leaf`. A tabela das 28 combinações é gravada e a checagem confere que a escolhida é a primeira dela.
- **Regras em português saem de `arvore.tree_`** (caminho raiz → folha), nunca escritas à mão.
- **Contraste reaproveita os hiperparâmetros da oficial**; `destination_region` vira colunas 0/1 com as categorias
  fixadas pelo treino.
- **Constantes novas em `config.py`, com a origem:** `COLUNAS_ARVORE`, `COLUNAS_PROIBIDAS`, `COLUNAS_CONTRASTE`,
  `ALVO`, `CLASSES`, `CRITERIO`, `SEMENTE`, `GRADE_PROFUNDIDADE`, `GRADE_FOLHA_MINIMA`, `MODELO` e os caminhos dos
  arquivos de `docs/data/modelo/`. Reaproveita `PASSOS_FUTURO` (folga) e `EXEMPLO_OK_Z_MAX` ("estável").
- **CSVs com `pandas.DataFrame.to_csv`**: `RelatorioRegiao.salvar_csv` recebe DataFrame do Spark e não serve aqui.

## Ordem e dependências

```
A1 dependências + dados + comando `arvore`
 └─ A2 métricas + persistência
     └─ A3 árvore oficial (grade)         ← checkpoint A (dono vê árvore × persistência)
         └─ A4 regras em português + erros concretos
             └─ A5 árvore de contraste
                 └─ A6 documentação + fechamento
```

Sequencial: todas passam por `modelo/execucao.py` e `config.py`.

## Lista de tarefas

### Fase 1: base
- [x] A1: Dependências, leitura dos dados e comando `arvore`
- [x] A2: Métricas e persistência

### Fase 2: a árvore
- [x] A3: Árvore oficial

### Checkpoint A (revisão do dono)
- [x] Árvore × persistência na validação e a árvore escolhida conferidas

### Fase 3: leitura e contraste
- [x] A4: Regras em português e erros concretos
- [x] A5: Árvore de contraste

### Fase 4: acabamento
- [x] A6: Documentação e fechamento

### Checkpoint final
- [ ] Todos os critérios de sucesso da spec marcados

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| A árvore não ganha da persistência | Médio | Previsto na RFC §9 e na spec: relata-se; checkpoint A antes de seguir |
| Folga aplicada depois do filtro de nulos (vazamento) | Alto | Ordem fixada em A1 + checagem automática das 3 últimas |
| `scikit-learn` / `pyarrow` sem pacote para o Python do `.venv` (3.14) | Médio | A1 começa pelo `uv add`; se falhar, parar e perguntar (fixar Python 3.11–3.13) |
| `NaN` rejeitado pela árvore | Alto | `scikit-learn>=1.4`; A3 treina com as 190 linhas sem RTT presentes; nunca imputar |
| `t` lido pelo pandas com fuso deslocado | Baixo | `t` só ordena e localiza linhas; blocos vêm da coluna `bloco`, não de `t` |
| Contraste não mostra o atalho da distância | Baixo | O alvo é relativo ao fluxo; relatar o resultado real |
| Recall de RISCO muito baixo sem balanceamento | Médio | Decisão do dono: vira o motivo do ajuste na Tarefa 4 |

## Questões em aberto

Nenhuma. Skills do catálogo: nenhuma tarefa pede uma que não esteja instalada.
