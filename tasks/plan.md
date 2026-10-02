# Plano de implementação: arquitetura medalhão (Bronze / Silver / Gold)

Spec: [`SPEC-medalhao.md`](../SPEC-medalhao.md) (aprovada em 30/09/2026). Tarefas detalhadas em [`todo.md`](todo.md).

## Visão geral

Hoje `python -m preditor` lê o BigQuery, calcula tudo em memória e grava em `data/processed/`. O plano
introduz uma camada por vez, de baixo para cima (Bronze → Silver → Gold). Ao fim de cada tarefa o pipeline
completo continua rodando, e no final os números do Gold são comparados com uma referência tirada antes de
qualquer mudança.

## Decisões de arquitetura

- **Referência antes de tudo (T1).** Roda-se o pipeline atual e guarda-se a saída em `data/_referencia/`
  (ignorada pelo git). É contra ela que o Gold é comparado; sem ela não há como provar que nada mudou.
- **A fronteira Bronze/Silver já existe no código.** `Medicoes.ler_bigquery()` vai para `bronze/ingestao.py`;
  `Medicoes.transformar()` fica em `silver/medicao.py` e passa a receber o Parquet do Bronze.
- **Cada camada lê a anterior do disco, nunca da memória.** Mesmo no pipeline completo, o Silver relê o Parquet
  do Bronze e o Gold relê o do Silver. Assim `python -m preditor` e `python -m preditor gold` percorrem o mesmo
  caminho, e o `.cache()` das medições deixa de ser necessário entre camadas.
- **CLI com `argparse`** (biblioteca padrão, sem dependência nova): argumento opcional `bronze | silver | gold`;
  sem argumento roda as três.
- **Uma função de leitura por camada** em `config.py`/`__main__.py` que verifica se a pasta existe e, se não,
  termina com a mensagem "rode `uv run python -m preditor <camada anterior>` antes".
- **Checagens por camada** ficam no `__main__.py`, junto das que já existem, e rodam logo após a gravação.
- **Gold muda de pasta por último (T4).** Até lá o cálculo do X continua gravando em `processed/`, para o
  pipeline nunca ficar quebrado no meio do caminho.

## Ordem e dependências

```
T1 referência + caminhos em config
 └─ T2 Bronze (ingestão + CLI)
     └─ T3 Silver (normalização lendo do Bronze)
         └─ T4 Gold (calculo_x / calculo_y dentro de gold/)
             └─ T5 comparação com a referência   ← checkpoint com o dono
                 └─ T6 documentação e limpeza
```

Tudo sequencial: cada camada depende da anterior e as tarefas mexem no mesmo `__main__.py`.

## Lista de tarefas

### Fase 1: base
- [x] T1: Referência da saída atual e caminhos das camadas em `config.py`
- [x] T2: Camada Bronze e CLI por camada

### Checkpoint A
- [ ] `python -m preditor bronze` grava o Bronze; `python -m preditor` continua produzindo a saída de hoje

### Fase 2: camadas
- [x] T3: Camada Silver lendo do Bronze
- [x] T4: Camada Gold (`gold/calculo_x`, `gold/calculo_y`)
- [x] T5: Comparação do Gold com a referência

### Checkpoint B (revisão do dono)
- [ ] Gold idêntico à referência; `silver` e `gold` rodam sem rede

### Fase 3: acabamento
- [x] T6: Documentação (`AGENTS.md`, `README.md`) e remoção de `processed/` e `_referencia/`

### Checkpoint final
- [ ] Todos os critérios de sucesso da spec marcados

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| A tabela inteira ser grande demais para baixar/guardar localmente | Alto | T2 mede o tamanho do Bronze logo no início; se for inviável, parar e voltar ao dono (a spec decidiu "tabela inteira") |
| A saída em `processed/` estar defasada em relação ao código atual | Médio | T1 roda o pipeline atual de novo antes de copiar a referência |
| Diferenças de ponto flutuante na última casa (ordem de soma após reler do Parquet) | Médio | T5 compara primeiro com `exceptAll`; se houver diferença, mede a maior diferença absoluta por coluna e leva ao dono antes de aceitar tolerância |
| Timestamps mudarem ao passar pelo Parquet e deslocarem o corte A/B | Alto | Sessão já fixa em UTC; T3 confere que o corte A/B impresso é o mesmo da referência |
| Sem credenciais do BigQuery na sessão de implementação | Médio | T1 e T2 precisam de rede; se faltar, o implementer para e pede ao dono para rodar os dois comandos |
| `__pycache__` antigos em `src/preditor/` darem a impressão de módulos que não existem mais | Baixo | T6 apaga os `__pycache__` das pastas removidas |

## Questões em aberto

Nenhuma. Skills do catálogo: nenhuma tarefa pede uma que não esteja instalada.
