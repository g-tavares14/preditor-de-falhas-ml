# Etapa 9: Validação (Real × Packet Tracer)


**Status:** comparação metodológica e avaliação simulada documentadas; equivalência real × simulado não comprovada.



| Critério | Repositório (RIPE Atlas) | Packet Tracer |
|---|---|---|
| Fonte dos dados | Anchors do RIPE Atlas; 81 fluxos (67 na coleta de referência) | Ping entre hosts simulados; 12 fluxos |
| Baseline (Período A) | 108 h, mínimo de 1.500 RTT válidos por fluxo | 20 rajadas de 3 pings por fluxo (reduzido) |
| Medição | Cerca de 3 pacotes a cada 240 s | Rajada manual de 3 pings |
| RTT normal | Ordem de 10 a 50 ms em rotas curtas e de 300 ms em rotas longas, conforme a referência da ATA | Valores simulados de poucos milissegundos, sem equivalência direta com as distâncias reais |
| País e região | Utilizados como metadados para identificar a localização das medições | Utilizados para organizar as 12 rotas simuladas; não são características do modelo |
| Cenários de teste | Comparação com resultados reais ainda pendente | 80 medições no Período B: Normal, Latência elevada, ICMP bloqueado e Queda de enlace |
| Classificação OK / RISCO / FALHA | Classificação de referência baseada nas regras do projeto original | Classificação preliminar: 32 OK, 8 RISCO e 40 FALHA; equivalência com os dados reais ainda não comprovada |


**Conclusão parcial:** o Cisco Packet Tracer permitiu realizar a coleta e a classificação preliminar dos cenários simulados. Entretanto, ainda não foi realizada uma comparação quantitativa com os resultados reais do RIPE Atlas. Portanto, não é possível afirmar que os dois ambientes apresentam o mesmo comportamento de classificação. Essa equivalência permanece pendente de validação.


## Avaliação experimental do modelo no Packet Tracer

Foi realizado o treinamento de uma árvore de decisão utilizando 80 medições do Período B, classificadas preliminarmente como OK, RISCO e FALHA.

O modelo utilizou a biblioteca scikit-learn, com profundidade máxima 4 e divisão estratificada dos dados.


| Métrica | Resultado |
|---|---|
| Medições utilizadas | 80 |
| Treinamento | 48 medições |
| Validação | 16 medições |
| Teste | 16 medições |
| Acurácia na validação | 93,75% |
| Acurácia no teste | 93,75% |



O modelo acertou 15 das 16 classificações na validação e 15 das 16 no teste.

Esses resultados demonstram que a árvore conseguiu reproduzir a maioria dos rótulos preliminares do Packet Tracer.

Entretanto, os rótulos foram gerados por regras e a divisão estratificada não preserva a ordem temporal. Portanto, os resultados não comprovam a previsão de falhas futuras nem a equivalência com os dados reais do RIPE Atlas.

A comparação quantitativa entre os dois ambientes permanece pendente.


## Comparação dos modelos de Machine Learning

O projeto original utiliza medições reais do RIPE Atlas e define um alvo de estado futuro com horizonte de aproximadamente 12 minutos. A árvore deste experimento classifica o estado atual.

No experimento desenvolvido no Cisco Packet Tracer,
utilizamos uma árvore de decisão para classificar o estado
atual da rede em OK, RISCO ou FALHA.


Os resultados experimentais da árvore de decisão estão
apresentados na seção anterior. Eles representam a
classificação preliminar das medições simuladas, e não
a previsão de falhas futuras.


Entretanto, os resultados não podem ser comparados
diretamente, pois os modelos possuem objetivos diferentes,
utilizam conjuntos de dados distintos e foram avaliados
por metodologias diferentes.

## Conclusão da Etapa 9

O experimento no Cisco Packet Tracer permitiu reproduzir,
em escala reduzida, etapas de coleta, classificação e
avaliação de dados de rede.

Foram realizadas 240 medições no Período A e 80 medições
no Período B, totalizando 320 medições simuladas.

Os quatro cenários do Período B foram:
Normal, Latência elevada, ICMP bloqueado e Queda de enlace.

A classificação preliminar produziu 32 registros OK,
8 registros RISCO e 40 registros FALHA.

Os resultados demonstram a execução do procedimento
experimental no ambiente simulado, mas não comprovam
equivalência com o comportamento da rede real nem
capacidade de prever falhas futuras.

A comparação quantitativa com o RIPE Atlas permanece
pendente por falta das métricas completas necessárias
para uma avaliação equivalente.


**Status final:** Comparação metodológica documentada e avaliação experimental concluída. A validação quantitativa com dados reais do RIPE Atlas permanece pendente.



## Resultado adicional: divisão temporal

A reavaliação cronológica (50% treino, 20% validação, 30% teste) utilizou 40, 16 e 24 medições, respectivamente. O treinamento teve 32 OK e 8 RISCO, sem exemplos de FALHA. A validação e o teste continham somente FALHA; ambos obtiveram **0% de acurácia**. A causa observada é a coleta sequencial dos cenários e a ausência da classe FALHA no conjunto de treinamento. Esse resultado limita a interpretação dos 93,75% da avaliação aleatória, que permanece documentada como experimento anterior.

**Escopo dos dados reais:** esta cópia do projeto não inclui o JSON bruto da coleta RIPE Atlas para uma reanálise independente. Uma comparação quantitativa anterior foi discutida durante o desenvolvimento, mas não é apresentada aqui como reprodutível a partir dos arquivos deste pacote. A equivalência entre os ambientes continua **não comprovada**.
