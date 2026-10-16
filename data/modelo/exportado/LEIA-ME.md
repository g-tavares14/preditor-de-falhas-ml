# Modelo exportado: preditor de degradação de rede

Gerado por `uv run python -m preditor exportar` (SPEC-comparacao-modelos.md, "Exportação"). Todos os números deste
arquivo vêm de `data/modelo/comparacao/` ou da própria exportação. Nada do teste (Tarefa 5) aparece aqui.

## O que há nesta pasta

| Arquivo | Tamanho | SHA-256 |
|---|---|---|
| `modelo_final.joblib` | 1,75 MB | `197579cba624b57c2d70c07e7db40524fc09d36ebfb7b9c083715e2d3809e48d` |
| `arvore_ajustada.joblib` | 9,5 KB | `9025233764c681d12ceff559e292463174180e8551397e9d95060d23fe094afd` |
| `exemplo_de_uso.py` | 1,8 KB | `f91c7eaff9ea2163b3782f74fc41f7343faa00f4dc1b46c03f4b89d196993633` |

- `modelo_final.joblib`: o modelo que a regra escolheu (random_forest), treinado só com o bloco de treino.
- `arvore_ajustada.joblib`: a árvore ajustada da Tarefa 4 (com peso de classe), em arquivo à parte. Ela é legível: as
  regras em português estão em `data/modelo/regras_arvore_ajustada.txt`.
- `exemplo_de_uso.py`: um exemplo curto que roda de qualquer pasta.

## Antes de abrir: segurança

> **Um `.joblib` é um pickle, e abrir um pickle executa código.** Só abra arquivos de fonte confiável. Antes de abrir,
> confira o SHA-256 da tabela:
>
> - macOS: `shasum -a 256 modelo_final.joblib`
> - Linux: `sha256sum modelo_final.joblib`

## O modelo escolhido

- Família: **random_forest**, pela regra da comparação: entre as candidatas, as que estão a até
  0,005 do maior F1 macro da validação, vence a mais simples (ordem: árvore, Random
  Forest, XGBoost).
  - ajustada_com_peso: F1 macro 0,685091 (fora da tolerância de 0,005)
  - random_forest: F1 macro 0,697714 (dentro da tolerância de 0,005)
  - xgboost: F1 macro 0,700588 (dentro da tolerância de 0,005)
- F1 macro na validação: **0,697714**. A persistência, na mesma validação, tem
  0,635522. O modelo supera a persistência: sim.
- Parâmetros (todos gravados em `modelo_final.joblib`):
  - `n_estimators`: 100
  - `max_depth`: 8
  - `min_samples_leaf`: 50
  - `max_features`: sqrt
  - `criterion`: gini
  - `class_weight`: {'OK': 1.0, 'RISCO': 2.0, 'FALHA': 1.5}
  - `semente`: 16
- Treino: 34.661 medições. Validação:
  13.490 (só para escolher e medir). Teste: fechado.

## As colunas de entrada, na ordem

O modelo espera exatamente estas 10 colunas, nesta ordem (o arquivo guarda a lista em `colunas`):

1. `z_robusto`: quantos desvios típicos o RTT está acima do normal do caminho (mediana e MAD do próprio caminho).
2. `aumento_pct`: aumento percentual do RTT sobre a mediana do caminho.
3. `jitter_relativo`: jitter da medição dividido pelo jitter típico do caminho (acima de 3 é alteração).
4. `perda_pct`: percentual de pings perdidos na medição.
5. `timeout_atual`: 1 se a medição teve timeout (nenhuma resposta), 0 se não.
6. `n5_timeout`: quantas das últimas 5 medições do caminho (incluindo esta) tiveram timeout.
7. `n5_aumento80`: quantas das últimas 5 medições tiveram aumento acima de 80 % sobre a mediana.
8. `n5_moderado`: quantas das últimas 5 medições tiveram alteração moderada (o critério de RISCO da RFC).
9. `min5_z`: o menor z_robusto das últimas 5 medições: alto só se o desvio se manteve nas 5.
10. `media5_z`: a média do z_robusto das últimas 5 medições.

Nenhuma coluna de região, país, IP, rota ou RTT absoluto entra no modelo (a RFC proíbe).

## Valores ausentes

Se uma medição não tem algum valor (por exemplo, o RTT não veio porque a sonda não respondeu), **deixe o valor
ausente**. O modelo aceita e não preenche: trocar por zero daria uma medição que não aconteceu. O `exemplo_de_uso.py` mostra
uma medição assim.

## A saída

O modelo devolve o texto da classe direto (`rotulos_do_modelo` é `None`).
A classe é a da **3ª medição à frente** do mesmo caminho, cerca de 12 minutos depois: OK, RISCO ou FALHA. Não é uma
leitura do que acontece agora.

## Versões usadas (para abrir, precisa de versões iguais ou compatíveis)

- python: 3.14.7
- scikit-learn: 1.9.1
- xgboost: 3.4.1
- numpy: 2.5.3
- pandas: 3.0.6
- joblib: 1.6.0

Outra versão do scikit-learn ou do XGBoost pode não abrir o arquivo, ou mudar as previsões. Se não abrir, confira a
versão acima.

## Como usar

```
python exemplo_de_uso.py
```

Precisa de scikit-learn, pandas e joblib (e de xgboost, se o modelo for o XGBoost). **Não precisa do pacote
`preditor`**: o arquivo só contém objetos dessas bibliotecas e da biblioteca padrão.

## Verificação feita na exportação

- Abrir `modelo_final.joblib` e `arvore_ajustada.joblib` em um processo novo reproduz exatamente as previsões da
  validação (13.490 medições).
- Uma medição sem nenhum valor é aceita e recebe uma das três classes.
- Só saem OK, RISCO e FALHA.
- O exemplo roda a partir de outra pasta.

## Limites que valem para o modelo

- Todos os números são da validação. O teste (Tarefa 5) continua fechado.
- A validação foi usada para escolher o modelo **e** para compará-lo, o que deixa a comparação levemente otimista.
- Ganho sobre a persistência: diferença de F1 macro +0,0622, IC 95 % de +0,0268 a +0,0750: tem prova (o intervalo não cruza o zero).
- Ganho sobre a árvore ajustada: diferença de F1 macro +0,0126, IC 95 % de -0,0017 a +0,0216: não tem prova (o intervalo cruza o zero).
  (`ic_pareado.csv`: IC de 95 % por fluxo, 2.000 reamostras; o IC que cruza o zero não prova o ganho.)
- O rótulo é uma política: a regra 3 da RFC com piso de 30 % de aumento. O modelo aprende essa definição, não a falha
  real do equipamento.
- Só serve para fluxos com ficha de baseline (1.500 medições válidas no período inicial).
