# Pergunta do modelo

## Pergunta única (canônica)

Com base neste histórico, neste período: a rede está **OK**, está em **RISCO**, ou vai **falhar (FALHA)**?

O modelo responde somente `OK | RISCO | FALHA` a partir da janela de medições
(`latencia_ms`, `perda_pacotes_pct`, `jitter_ms` e, se útil, features de traceroute).
Não existe outra pergunta de produto nesta versão do projeto — classificação e
diagnóstico não se misturam.

## Classes e regra de rótulo de referência

O rótulo `status_real` segue a regra:

1. `perda_pacotes_pct` > 15 → **FALHA**
2. senão, `latencia_ms` > 100 → **RISCO**
3. senão → **OK**

## Apoio ao diagnóstico (não são perguntas do modelo)

TTL, hops, destino longo vs. estável, `rtt_max` e `prb_id` ajudam a explicar
**por que** o rótulo saiu daquele jeito, para uso na defesa e no dashboard.
Eles **não** viram classes novas nem perguntas separadas do modelo.

## Fora de escopo

- Previsão multi-horizonte (prever várias janelas futuras de uma vez).
- Regressão de RTT (estimar o valor exato da latência, em vez de classificar).
- Treino da árvore de decisão / modelo em si.
- Dashboard.
- Coleta via RIPE Atlas e infraestrutura AWS (documentados em `docs/dataset-fonte-atlas.md` e `docs/aws_lambda.md`).

## Verificação

Alguém de fora da equipe precisa conseguir explicar a pergunta do modelo em
uma frase, sem citar TTL ou hops.

## Notebook didático de cálculo de Y

`notebooks/03_calculo_status_real.ipynb` demonstra o cálculo de Y (`status_real`)
com uma cópia local do curated canônico `curated/log_rede.csv`, salva em
`data/curated/log_rede.csv` para executar o notebook. A regra continua em
`src/preditor_de_falhas_ml/features.py`; o notebook recalcula o rótulo em memória,
compara com o valor existente e exibe a distribuição e casos de exemplo. Não
altera o CSV, grava no S3 ou treina o modelo. Valores ausentes seguem o
comportamento da função oficial.
