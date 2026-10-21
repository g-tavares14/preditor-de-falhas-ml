# Etapa 8: Classificação OK / RISCO / FALHA

**Status:** classificação experimental executada; regras comparadas com o original; avaliação temporal realizada com limitações.

Os critérios de classificação apresentados nesta etapa correspondem às regras implementadas no arquivo `classificar_medicoes.py`. A classificação é preliminar e ainda depende de validação em relação aos requisitos do projeto original.

| Métrica | OK | RISCO | FALHA |
|---|---|---|---|
| `latencia_relativa` / `z_robusto` | Sem desvio moderado recorrente ou condição de falha | Z entre 2 e 3,5 ou aumento de latência entre 30% e 80%, com pelo menos 2 desvios moderados nas últimas 5 medições | Z ≥ 3,5 com aumento ≥ 30%, ou pelo menos 2 aumentos acima de 80% nas últimas 5 medições |
| `jitter_relativo` | Sem desvio moderado recorrente | Jitter relativo ≥ 3, com pelo menos 2 desvios moderados nas últimas 5 medições | Não determina FALHA isoladamente nas regras implementadas |
| `perda_pct` e `timeout_atual` | Perda abaixo de 10% e menos de 3 timeouts nas últimas 5 medições | Não determinam RISCO isoladamente nas regras implementadas | Perda ≥ 10% ou pelo menos 3 timeouts nas últimas 5 medições |


A árvore experimental foi avaliada com divisão aleatória e, separadamente, com divisão temporal; os resultados não são diretamente comparáveis.

## Resultados da classificação preliminar

Foram analisadas 80 medições do Período B, utilizando os dados coletados no Cisco Packet Tracer.

| Cenário | OK | RISCO | FALHA |
|---|---:|---:|---:|
| Normal | 16 | 4 | 0 |
| Latência elevada | 16 | 4 | 0 |
| ICMP bloqueado | 0 | 0 | 20 |
| Queda de enlace | 0 | 0 | 20 |
| **Total** | **32** | **8** | **40** |

A classificação preliminar foi realizada com Python, utilizando o arquivo `classificar_medicoes.py`.

O resultado foi exportado para `data/classificacao_preliminar.csv`, contendo 80 medições classificadas.

**Limitações:** a baseline utilizada contém 20 medições por fluxo, abaixo das 1.500 medições válidas exigidas pelo projeto original. A correspondência das principais regras foi conferida, mas a equivalência integral não foi demonstrada.
  
  
## Treinamento experimental da árvore de decisão

Foi realizado um experimento de aprendizado de máquina utilizando o algoritmo DecisionTreeClassifier, da biblioteca scikit-learn, por meio do arquivo `treinar_arvore.py`.

Foram utilizadas 80 medições do Período B, com as classificações preliminares OK, RISCO e FALHA.

Os dados foram divididos de forma estratificada em:
- Treinamento: 48 medições (60%)
- Validação: 16 medições (20%)
- Teste: 16 medições (20%)

### Comparação dos modelos

| Métrica | Profundidade 3 | Profundidade 4 |
|---|---:|---:|
| Acurácia na validação | 87,50% | 93,75% |
| Acurácia no teste | 93,75% | 93,75% |
| Acertos de RISCO na validação | 1 de 2 | 2 de 2 |
| Acertos de RISCO no teste | 0 de 1 | 1 de 1 |

A árvore com profundidade máxima 4 apresentou melhor desempenho na validação e foi mantida como configuração experimental.

### Resultado da árvore com profundidade 4

Na validação, foram classificadas corretamente 15 das 16 medições, resultando em acurácia de 93,75%.

No teste, também foram classificadas corretamente 15 das 16 medições, com acurácia de 93,75%.

O modelo apresentou um erro na validação, classificando uma medição OK como FALHA, e um erro no teste, classificando uma medição OK como RISCO.

### Limitações

O treinamento utilizou rótulos preliminares gerados por regras, e não rótulos independentes de falhas futuras.

A divisão estratificada mistura períodos e cenários, não representando uma avaliação cronológica de previsão.

A classe RISCO possui apenas 8 exemplos no conjunto completo, o que limita a confiabilidade da avaliação.

Portanto, os resultados demonstram a capacidade experimental de reproduzir classificações preliminares, mas não comprovam a previsão de falhas futuras nem a equivalência com o projeto original.


## Conferência das regras com o projeto original

Foram examinados `config.py`, `baseline.py`, `features.py` e `rotulo.py` do projeto original. Os limiares das regras OK/RISCO/FALHA e as fórmulas principais de mediana, MAD, IQR, aumento percentual e Z robusto correspondem aos utilizados nesta adaptação. Foi corrigido o caso MAD = 0: aplica-se `max(IQR / 1,349; 1 ms)`. A reexecução produziu 32 OK, 8 RISCO e 40 FALHA.

A correspondência é parcial: o projeto original exige 1.500 RTT válidos por fluxo, enquanto a simulação tem baseline reduzido; há diferenças possíveis na seleção de valores para o jitter típico. Não foi realizada uma comparação linha a linha com a execução Spark original.

## Avaliação cronológica (50% / 20% / 30%)

A árvore foi reavaliada em ordem de `timestamp`, com 40 medições no treinamento, 16 na validação e 24 no teste.

| Conjunto | Classes observadas | Acurácia |
|---|---|---:|
| Treinamento (40) | 32 OK; 8 RISCO; nenhuma FALHA | — |
| Validação (16) | 16 FALHA | 0% |
| Teste (24) | 24 FALHA | 0% |

Os cenários foram coletados sequencialmente. Por isso, a árvore não viu exemplos de FALHA no treinamento e não pôde aprender essa classe. A avaliação aleatória anterior (93,75% na validação e no teste) é mantida acima apenas como histórico experimental, não como comprovação de generalização temporal.

O alvo usado é `status_atual`, derivado das regras; o original usa `status_futuro` com horizonte de aproximadamente 12 minutos. Assim, **não foi demonstrada previsão de falhas futuras**.
