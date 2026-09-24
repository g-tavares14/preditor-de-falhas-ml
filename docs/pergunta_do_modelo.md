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

`notebooks/03_calculo_status_real.ipynb` demonstra a criação de Y (`status_real`)
a partir do arquivo local `data/raw/features.csv`, baixado do S3 para esta
atividade. O notebook importa `status_real` de `src/preditor_de_falhas_ml/features.py`;
essa função continua sendo a fonte canônica da regra e não é reimplementada nas
células. O notebook exibe a distribuição resultante e casos de exemplo, sem
alterar o CSV, gravar em S3 ou treinar o modelo. O comportamento para valores
ausentes acompanha a função existente: `FALHA` se a perda conhecida passar de
15%, `RISCO` se a latência conhecida passar de 100 ms e `OK` quando nenhuma
condição for satisfeita.
