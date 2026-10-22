# Previsão de Falhas em Redes de Computadores Utilizando Aprendizado de Máquina: uma Comparação entre Decision Tree, Random Forest e XGBoost

**Autores:** Alexandre Tiago de Oliveira; Guilherme Leite Tavares; Ingrid Ferreira de Sousa; Kauan Garcia Dias de Oliveira; Lucas Eduardo Malachias Bagatela; Stephanie Vitoria Bessa dos Santos.

**Instituição:** Universidade Braz Cubas  
**Curso:** Ciência da Computação  
**Disciplina:** Estrutura de dados II  
**Turma:** 3º período

**Repositório do projeto:** https://github.com/g-tavares14/preditor-de-falhas-ml

## Resumo

A identificação antecipada de falhas em redes de computadores é importante para reduzir interrupções e melhorar a disponibilidade dos serviços. Este trabalho apresenta o desenvolvimento de um sistema de previsão de estados da rede utilizando técnicas de aprendizado de máquina. Foram comparados três algoritmos: Decision Tree, Random Forest e XGBoost, utilizando medições públicas de conectividade disponibilizadas pela plataforma RIPE Atlas. Os estados foram classificados em OK, RISCO e FALHA, com base em indicadores como latência, perda de pacotes e variações em relação ao comportamento normal de cada fluxo. Na validação, o XGBoost apresentou o maior F1 macro, de aproximadamente 0,7006, enquanto o Random Forest alcançou 0,6977. Seguindo uma regra de seleção previamente definida, o Random Forest foi escolhido por apresentar desempenho próximo ao melhor resultado e atender ao critério de preferência pelo modelo mais simples entre os candidatos elegíveis. No teste final, o modelo obteve F1 macro de 0,6699, superando a estratégia de persistência, que alcançou 0,6132. Apesar do resultado positivo, foram observadas limitações na identificação de falhas, indicando a necessidade de aprimoramentos.

**Palavras-chave:** Aprendizado de máquina; Redes de computadores; Previsão de falhas; Random Forest; XGBoost.

## 1. Introdução

As redes de computadores são essenciais para o funcionamento de sistemas, aplicações e serviços digitais. Problemas como aumento da latência, perda de pacotes e interrupções de conectividade podem prejudicar o desempenho e a disponibilidade desses serviços.

Tradicionalmente, o monitoramento de redes utiliza métricas e limites predefinidos para identificar comportamentos anormais. Entretanto, essas abordagens podem apresentar dificuldades para reconhecer padrões complexos e mudanças que antecedem uma falha.

Nesse contexto, o aprendizado de máquina oferece recursos para analisar dados históricos e identificar padrões que auxiliem na previsão de possíveis problemas.

Este trabalho tem como objetivo desenvolver e avaliar um sistema de previsão de estados de rede, comparando os algoritmos Decision Tree, Random Forest e XGBoost. A proposta é verificar se esses modelos conseguem identificar situações de risco ou falha com antecedência, utilizando medições reais de conectividade.

A pesquisa também considera uma estratégia simples de referência, denominada persistência, que assume que o próximo estado será igual ao estado atual. Dessa forma, é possível verificar se os modelos de aprendizado de máquina oferecem benefícios em relação a essa abordagem.

## 2. Fundamentação teórica

### 2.1 Decision Tree

O Decision Tree, ou Árvore de Decisão, é um algoritmo de aprendizado supervisionado que organiza decisões em uma estrutura de árvore. Cada divisão utiliza características dos dados para encaminhar uma observação até uma classe prevista.

Uma de suas principais vantagens é a facilidade de interpretação, pois permite compreender quais condições contribuíram para determinada classificação. Entretanto, árvores muito complexas podem se ajustar excessivamente aos dados de treinamento, reduzindo a capacidade de generalização.

### 2.2 Random Forest

O Random Forest é um algoritmo que combina várias árvores de decisão. Cada árvore é treinada com variações dos dados e das características disponíveis, e as previsões são combinadas para produzir a classificação final.

Essa combinação tende a reduzir a variabilidade de uma árvore individual e pode melhorar a capacidade de generalização. Em contrapartida, interpretar o conjunto de árvores pode ser mais difícil do que interpretar uma única árvore.

### 2.3 XGBoost

O XGBoost é uma implementação de gradient boosting que constrói árvores sequencialmente. Cada nova etapa busca melhorar o desempenho do conjunto, considerando os erros cometidos anteriormente.

O algoritmo possui recursos de regularização e otimização que podem contribuir para bons resultados em dados estruturados. Entretanto, sua configuração exige atenção aos hiperparâmetros para evitar sobreajuste e controlar a complexidade do modelo.

### 2.4 Estratégia de persistência

A persistência é utilizada como referência para a avaliação dos modelos. Ela considera que o estado futuro será igual ao estado observado no momento atual.

Essa abordagem é simples e pode funcionar bem quando a rede permanece estável. Porém, não consegue antecipar adequadamente as situações em que o estado muda.

## 3. Materiais e métodos

### 3.1 Fonte e caracterização dos dados

Foram utilizadas medições públicas de ping da plataforma RIPE Atlas, coletadas no período de 18 a 25 de setembro de 2026. O conjunto inicial contemplou 82 fluxos de medição, dos quais 79 possuíam dados suficientes para o procedimento adotado.

Os dados foram organizados temporalmente em conjuntos de treinamento, validação e teste, respeitando a sequência das medições. Essa separação busca aproximar a avaliação de um cenário em que o modelo utiliza dados anteriores para prever comportamentos posteriores.

A distribuição foi organizada da seguinte forma:

- **Treinamento:** 34.661 registros com o rótulo futuro disponível.
- **Validação:** 13.490 registros com o rótulo futuro disponível.
- **Teste final:** 20.507 registros com o rótulo futuro disponível.

O conjunto de treinamento corresponde ao período de 22 a 23 de setembro; o de validação, ao período de 23 a 24 de setembro; e o teste, ao período de 24 a 25 de setembro de 2026.

Os três conjuntos foram definidos cronologicamente, evitando uma divisão aleatória que pudesse misturar observações passadas e futuras.

### 3.2 Definição dos estados da rede

O sistema utiliza três classes:

- **OK:** representa condições consideradas normais em relação ao comportamento de referência do fluxo.
- **RISCO:** representa alterações que indicam degradação ou comportamento potencialmente problemático.
- **FALHA:** representa situações que atendem aos critérios definidos pelo projeto para caracterizar uma condição mais severa.

A classificação é baseada em regras elaboradas para o projeto, considerando alterações nas medições e desvios em relação ao comportamento normal de cada fluxo.

Para definir a referência, foi utilizada a mediana da latência observada durante as primeiras 108 horas de cada fluxo, com exigência mínima de 1.500 medições válidas. Também foi utilizada a mediana dos desvios absolutos, conhecida como MAD, para reduzir a influência de valores extremos.

O projeto incluiu um limite mínimo de aumento de 30% na latência em uma das regras de classificação de FALHA. Esse ajuste foi adotado após a análise de falsos positivos, pois o critério baseado apenas em desvio robusto identificava muitas ocorrências em fluxos relativamente estáveis.

É importante destacar que as classes representam os critérios operacionais definidos pelo projeto. Portanto, uma previsão de FALHA não comprova, por si só, que ocorreu uma falha física em um roteador ou equipamento.

### 3.3 Características utilizadas

Foram utilizadas dez características para representar o comportamento recente de cada fluxo, considerando informações relativas ao seu próprio padrão normal.

Entre os indicadores considerados estão variações recentes de latência, histórico de medições alteradas, perda de pacotes e ocorrências de timeout.

A utilização de medidas relativas ao comportamento de cada fluxo busca evitar que diferenças naturais de latência entre caminhos de rede sejam confundidas com falhas.

O objetivo é identificar mudanças no comportamento de uma conexão, e não apenas comparar valores absolutos de latência entre diferentes fluxos.

### 3.4 Definição da previsão

O objetivo dos modelos foi prever o estado futuro do fluxo, considerando a terceira medição posterior à observação de referência, o que corresponde a um horizonte aproximado de 10 a 14 minutos, dependendo da frequência das medições.

Essa abordagem permite avaliar se os dados disponíveis contêm sinais úteis para antecipar mudanças no estado da rede.

### 3.5 Treinamento e seleção dos modelos

Os algoritmos Decision Tree, Random Forest e XGBoost foram treinados e comparados por meio das métricas calculadas no conjunto de validação.

Foram exploradas diferentes configurações de hiperparâmetros. No Random Forest, a configuração selecionada utilizou 100 árvores, profundidade máxima de 8, mínimo de 50 amostras por folha e seleção de características pelo método sqrt. Também foram aplicados pesos às classes para considerar as diferenças na distribuição dos estados.

Para o XGBoost, a configuração considerada utilizou 300 árvores no total, taxa de aprendizado de 0,1 e profundidade máxima de 4.

A escolha final seguiu uma regra previamente estabelecida: selecionar o modelo mais simples entre os candidatos cujo F1 macro estivesse a, no máximo, 0,005 do maior valor observado na validação. Por esse critério, o Random Forest foi escolhido em vez do XGBoost.

Essa decisão não significa que o Random Forest apresentou a maior pontuação de validação, mas que ficou suficientemente próximo do melhor resultado e atendeu à regra de seleção definida.

### 3.6 Métricas de avaliação

Foram utilizadas as seguintes métricas:

- **Acurácia:** proporção de previsões corretas entre todas as observações.
- **Precisão:** proporção das previsões positivas de uma classe que realmente pertencem a ela.
- **Recall:** proporção das observações reais de uma classe que foram identificadas corretamente.
- **F1-score:** média harmônica entre precisão e recall.
- **F1 macro:** média do F1-score das classes, atribuindo o mesmo peso a cada uma.

O F1 macro é especialmente relevante neste projeto porque as classes apresentam frequências diferentes. Assim, uma boa acurácia geral não garante que o modelo consiga reconhecer adequadamente a classe FALHA.

## 4. Resultados e discussão

### 4.1 Comparação dos modelos na validação

A Tabela 1 apresenta os principais resultados de validação obtidos pelos modelos e pela estratégia de persistência.

**Tabela 1 – Resultados no conjunto de validação**

| Modelo | Acurácia | F1 macro | F1 da classe FALHA | Recall de FALHA |
|---|---:|---:|---:|---:|
| Persistência | 81,7% | 0,6355 | 0,500 | 49,8% |
| Decision Tree – configuração inicial | 85,9% | 0,6860 | 0,580 | 47,8% |
| Decision Tree – configuração ajustada | 85,2% | 0,6851 | 0,566 | 50,5% |
| Random Forest | 85,5% | 0,6977 | 0,599 | 50,5% |
| XGBoost | 85,5% | 0,7006 | 0,598 | 51,4% |

**Fonte:** resultados dos experimentos do projeto.

O XGBoost apresentou o maior F1 macro, aproximadamente 0,7006, seguido pelo Random Forest, com 0,6977. A diferença entre os dois foi pequena, de aproximadamente 0,0029.

O Random Forest apresentou F1 da classe FALHA de 0,599, enquanto o XGBoost alcançou 0,598. Já o recall de FALHA foi ligeiramente maior no XGBoost, com 51,4%, contra 50,5% no Random Forest.

A Decision Tree apresentou resultados superiores aos da persistência no F1 macro, mas inferiores aos dos modelos de conjunto na comparação principal. A versão ajustada da árvore obteve F1 macro de 0,6851.

Os resultados indicam que os modelos de aprendizado de máquina conseguiram melhorar diferentes métricas em relação à persistência. Entretanto, nenhum deles identificou todas as ocorrências de falha, demonstrando que a previsão antecipada continua sendo um desafio.

### 4.2 Avaliação do teste final

Após a seleção, o Random Forest foi avaliado em um conjunto de teste final com 20.507 observações. Essa etapa comparou o modelo selecionado com a estratégia de persistência.

**Importante:** o teste final apresentado nesta seção compara somente o Random Forest e a persistência. Os valores de Decision Tree e XGBoost apresentados anteriormente são resultados de validação, não de teste final.

**Tabela 2 – Resultados no teste final**

| Métrica | Random Forest | Persistência |
|---|---:|---:|
| Acurácia | 83,96% | 79,53% |
| F1 macro | 0,6699 | 0,6132 |
| F1 da classe FALHA | 0,4946 | 0,4324 |
| Recall da classe FALHA | 38,16% | 43,12% |
| Precisão da classe FALHA | 70,25% | 43,36% |
| Acurácia balanceada | 0,6361 | 0,6131 |

**Fonte:** resultados do teste final do projeto.

O Random Forest apresentou F1 macro de 0,6699, enquanto a persistência alcançou 0,6132, representando um ganho de 0,0567. A acurácia também foi superior, passando de 79,53% para 83,96%.

A precisão da classe FALHA chegou a 70,25%, indicando que, entre as observações classificadas pelo Random Forest como FALHA, uma proporção elevada correspondia realmente a essa classe de referência.

Por outro lado, o recall de FALHA foi de 38,16%, inferior aos 43,12% obtidos pela persistência. Isso demonstra uma limitação importante: apesar de apresentar menos previsões falsas de falha, o Random Forest deixou de identificar uma parcela significativa das falhas reais.

O ganho de F1 macro no teste foi positivo, com intervalo de confiança de 95% por fluxo entre 0,0168 e 0,0658, conforme a análise do projeto. Esse resultado deve ser interpretado considerando a quantidade limitada de fluxos e o período relativamente curto de coleta.

### 4.3 Matriz de confusão do Random Forest

A matriz de confusão permite analisar como as observações de cada classe foram classificadas pelo modelo no teste final.

**Tabela 3 – Matriz de confusão do Random Forest**

| Classe real | Previsto OK | Previsto RISCO | Previsto FALHA | Total real |
|---|---:|---:|---:|---:|
| OK | 14.631 | 944 | 143 | 15.718 |
| RISCO | 1.371 | 2.109 | 59 | 3.539 |
| FALHA | 375 | 398 | 477 | 1.250 |
| **Total previsto** | **16.377** | **3.451** | **679** | **20.507** |

**Fonte:** resultados do teste final do projeto.

Das 1.250 observações reais da classe FALHA, o modelo identificou corretamente 477. Outras 398 foram classificadas como RISCO e 375 como OK.

Esses resultados mostram que o modelo teve dificuldade para reconhecer todas as falhas, especialmente quando os sinais anteriores não eram suficientemente claros.

Também é possível observar que o modelo classificou apenas 59 observações reais da classe RISCO como FALHA. Isso sugere um comportamento conservador ao atribuir a classe mais severa.

### 4.4 Capacidade de antecipar mudanças

Outro aspecto relevante é a diferença entre observações em que o estado futuro permaneceu igual ao atual e aquelas em que houve mudança.

No teste final, 16.309 observações mantiveram o mesmo estado, enquanto 4.198 apresentaram mudança.

O Random Forest obteve aproximadamente 96,2% de acurácia nas observações sem mudança, mas apenas 36,4% nas observações em que o estado mudou.

A persistência, por definição, acerta quando o estado permanece igual e erra quando há mudança. Portanto, embora o Random Forest tenha superado a persistência nas métricas gerais, sua capacidade de antecipar alterações permanece limitada.

Esse ponto é especialmente importante para o objetivo do projeto: um sistema de previsão de falhas precisa reconhecer não apenas condições estáveis, mas também mudanças que podem indicar degradação futura.

### 4.5 Interpretação geral

Os experimentos indicam que o aprendizado de máquina pode melhorar a classificação dos estados da rede em comparação com uma estratégia simples de persistência.

Na validação, o XGBoost apresentou o maior F1 macro, enquanto o Random Forest ficou muito próximo. No teste final, o Random Forest superou a persistência no F1 macro e na acurácia, mas apresentou recall inferior para a classe FALHA.

Assim, os resultados não permitem afirmar que o sistema já seja capaz de antecipar todas as falhas com segurança. O principal benefício observado foi a melhoria do desempenho geral e da precisão das previsões de FALHA, acompanhada da necessidade de aprimorar a identificação de ocorrências reais dessa classe.

## 5. Limitações e trabalhos futuros

O projeto apresenta limitações que devem ser consideradas na interpretação dos resultados.

Primeiramente, os dados abrangem aproximadamente sete dias de medições e 79 fluxos com dados suficientes. Essa quantidade limita a capacidade de generalizar os resultados para outros períodos, rotas ou redes.

Além disso, os mesmos fluxos aparecem nos conjuntos de treinamento, validação e teste, embora em períodos diferentes. Portanto, o teste avalia o comportamento em observações posteriores dos fluxos analisados, mas não comprova a generalização para fluxos totalmente desconhecidos.

Outra limitação é que as classes são determinadas por regras definidas no projeto. Uma classificação como FALHA não representa necessariamente uma falha física confirmada, mas uma condição que atende aos critérios adotados.

O uso de uma referência fixa baseada nas primeiras 108 horas também pode dificultar a adaptação a mudanças permanentes no comportamento da rota. Além disso, o recall de FALHA de 38,16% no teste mostra que muitas ocorrências ainda não são identificadas.

Como trabalhos futuros, recomenda-se:

- Ampliar o período de coleta e a quantidade de fluxos analisados.
- Avaliar o desempenho em fluxos que não participaram do treinamento.
- Aprimorar as características que ajudam a identificar o início de uma falha.
- Investigar estratégias de balanceamento das classes.
- Avaliar diferentes horizontes de previsão.
- Revisar os critérios de rotulagem com dados adicionais de referência.
- Monitorar a estabilidade dos modelos diante de mudanças no comportamento da rede.

## 6. Conclusão

Este trabalho apresentou o desenvolvimento e a avaliação de um sistema de previsão de estados de redes de computadores utilizando Decision Tree, Random Forest e XGBoost.

Na validação, o XGBoost apresentou o maior F1 macro, aproximadamente 0,7006, seguido pelo Random Forest, com 0,6977. Conforme a regra de seleção definida previamente, o Random Forest foi escolhido por apresentar desempenho próximo ao melhor resultado e atender ao critério de preferência pelo modelo mais simples entre os candidatos elegíveis.

No teste final, o Random Forest alcançou F1 macro de 0,6699, superando a persistência, que obteve 0,6132. Entretanto, seu recall da classe FALHA foi de 38,16%, evidenciando que uma parcela considerável das falhas não foi identificada.

Conclui-se que o aprendizado de máquina demonstrou potencial para melhorar a classificação dos estados da rede, mas ainda existem desafios para antecipar falhas com maior confiabilidade. A ampliação da base de dados, a melhoria das características utilizadas e a avaliação em fluxos desconhecidos são caminhos importantes para a evolução do sistema.

## Referências

CHEN, Tianqi; GUESTRIN, Carlos. XGBoost: A Scalable Tree Boosting System. In: *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*. 2016.

BREIMAN, Leo. Random Forests. *Machine Learning*, v. 45, p. 5–32, 2001.

RIPE NCC. **RIPE Atlas**. Plataforma de medições e monitoramento da conectividade da Internet. Disponível em: https://atlas.ripe.net/. Acesso em: 21 out. 2026.

SCIKIT-LEARN. **Decision Trees**. Documentação oficial. Disponível em: https://scikit-learn.org/stable/modules/tree.html. Acesso em: 21 out. 2026.

SCIKIT-LEARN. **Ensemble methods: Random Forests**. Documentação oficial. Disponível em: https://scikit-learn.org/stable/modules/ensemble.html#forest. Acesso em: 21 out. 2026.

## Reprodutibilidade

O código-fonte, os componentes do projeto e os materiais disponíveis para reprodução dos experimentos podem ser consultados no repositório:

https://github.com/g-tavares14/preditor-de-falhas-ml

Para reproduzir os resultados, recomenda-se consultar as instruções do README e utilizar a versão do código correspondente aos experimentos relatados neste artigo.

## Sobre os autores

**Alexandre Tiago de Oliveira**  
Graduando em Ciência da Computação pela Universidade Braz Cubas. Contribuiu para o desenvolvimento geral do projeto, incluindo a implementação, integração e análise dos componentes do sistema.

**Guilherme Leite Tavares**  
Graduando em Ciência da Computação pela Universidade Braz Cubas. Contribuiu para o desenvolvimento técnico do projeto, incluindo os componentes de aprendizado de máquina e a integração das funcionalidades do sistema.

**Ingrid Ferreira de Sousa**  
Graduanda em Ciência da Computação pela Universidade Braz Cubas. Contribuiu com a área de redes de computadores, auxiliando na análise das medições de conectividade, latência, perda de pacotes e critérios de classificação dos estados da rede.

**Kauan Garcia Dias de Oliveira**  
Graduando em Ciência da Computação pela Universidade Braz Cubas. Contribuiu com a documentação técnica, a organização dos diagramas e a descrição dos processos e da estrutura do projeto.

**Lucas Eduardo Malachias Bagatela**  
Graduando em Ciência da Computação pela Universidade Braz Cubas. Contribuiu com a elaboração e organização da documentação, dos diagramas e da representação dos componentes e fluxos do sistema.

**Stephanie Vitoria Bessa dos Santos**  
Graduanda em Ciência da Computação pela Universidade Braz Cubas. Contribuiu com a análise dos dados de redes, o estudo dos indicadores de desempenho e o apoio à definição dos critérios utilizados para classificar os estados da rede.