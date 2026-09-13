# Memorando de decisão — Fonte de dados

| Campo | Informação |
|---|---|
| Curso / disciplina | Estrutura de Dados II |
| Projeto integrador | Preditor de falhas ML |
| Orientador(a) | Andrea Ono Sakai |
| Data de entrega | 08/09/2026 |
| Data de revisão | 12/09/2026
| Integrantes | Alexandre Tiago de Oliveira, Ingrid Ferreira de Sousa, Guilherme Leite Tavares, Kauan Garcia Dias de Oliveira, Lucas Eduardo Malachias Bagatela, Stephanie Vitoria Bessa dos Santos |

> Este documento usa como base a pesquisa sobre o PingER, a documentação oficial do RIPE Atlas e as instruções do template do memorando.
>**Arquivo vivo**:este memorando será revisado confrome o estado do pipeline e das decisões técnicas do projeto evoluírem 

## 1. Situação

É preciso escolher uma fonte de dados para o pipeline que pretende trabalhar com latência, perda de pacotes e jitter, comparando o dataset histórico PingER com medições coletadas pela API do RIPE Atlas.

## 2. Opção A — Dataset real PingER

- **Origem / acesso:** [PingER — SLAC](https://www.slac.stanford.edu/comp/net/wan-mon.html) e [tutorial de acesso aos dados](https://www.slac.stanford.edu/comp/net/wan-mon/tutorial.html).
- **Formato:** Dados brutos de ping e relatórios resumidos disponíveis na Web; os relatórios resumidos podem ser obtidos em formato TSV compatível com planilhas.
- **Período coberto:** Há histórico público desde 1998. As medições tradicionais são feitas aproximadamente a cada 30 minutos, com séries por monitor e destino.
- **Campos disponíveis:** Monitor/origem, destino, timestamp, tamanho do pacote, pacotes enviados e recebidos, RTT mínimo/médio/máximo, perda de pacotes, indisponibilidade e jitter. Alguns relatórios também apresentam throughput derivado e métricas de qualidade.
- **Licença:** Não foi identificada uma licença aberta específica nas páginas consultadas. O uso deve manter a atribuição ao projeto PingER/SLAC e os termos de acesso devem ser confirmados antes de redistribuir os dados.

### Resumo

O PingER usa requisições e respostas ICMP Echo para medir o desempenho entre pontos de monitoramento e destinos remotos. Cada amostra registra os resultados de vários pings, permitindo calcular diretamente latência/RTT e perda; o jitter representa a variação dos RTTs. A existência de timestamp e de medições repetidas permite organizar os dados em janelas temporais.

Essa opção é adequada para o vetor definido no projeto: `X = [latência, perda, jitter]`. A principal limitação é que o PingER é um arquivo histórico de medições já realizadas, e não uma coleta controlada pela equipe. Além disso, os dados não têm rótulo explícito de “falha”; esse rótulo precisará ser definido a partir de regras ou eventos observados.

## 3. Opção B — API do RIPE Atlas

- **Documentação:** [RIPE Atlas — Authentication](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/), [Creating Measurements](https://beta-ui.atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/), [Measurement Results](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results) e [Measurement Result Format](https://atlas.ripe.net/docs/apis/measurement-result-format/).
- **Autenticação:** Consultas públicas podem ser feitas sem autenticação em vários endpoints. Para criar medições, é necessária uma chave de API com permissão de criação.
- **Como criar uma medição:** Enviar um `POST` para `https://atlas.ripe.net/api/v2/measurements/`, informando o tipo da medição, o alvo, a família de endereços e a seleção de probes. Para o projeto, o tipo mais relevante é `ping`.
- **Como consultar os resultados:** Usar `GET /api/v2/measurements/{id}/results/`, com filtros opcionais por probe e período. A resposta contém os resultados das medições, que podem ser transformados em latência, perda e jitter.

### Resumo

O RIPE Atlas permite coletar medições de rede distribuídas e repetidas, com controle sobre alvo, probes, intervalo e duração. Os resultados de ping incluem timestamp, pacotes enviados/recebidos e estatísticas de RTT, mas o jitter precisa ser calculado a partir da variação dos RTTs. Em contrapartida, a opção exige configuração da coleta, controle de créditos e tratamento dos resultados.

## 4. Comparação

| Critério | Opção A — PingER | Opção B — RIPE Atlas |
|---|---|---|
| Controle sobre a coleta | Baixo: os dados já foram coletados | Alto: a equipe define alvo, probes, frequência e duração |
| Diversidade geográfica | Alta, com diferentes monitores e destinos históricos | Alta, conforme a seleção de probes disponíveis |
| Custo e complexidade | Baixos a médios: acesso, seleção e limpeza dos relatórios | Médios: exige API, créditos, coleta e tratamento contínuos |
| Tempo até os primeiros dados | Rápido, após selecionar e baixar os relatórios | Depende da criação e execução da medição |
| Latência, perda e jitter | Disponíveis diretamente ou derivados dos pings | Disponíveis diretamente ou derivados dos resultados |
| Controle sobre o período futuro | Nenhum | Alto: a equipe agenda novas medições |

## 5. Recomendação

Para a primeira versão do pipeline, foi adotada a **Opção B — API do RIPE Atlas**, mantendo o PingER como referência histórica e possível fonte complementar.

## 6. Justificativa

O objetivo atual exige dados temporais de latência, perda de pacotes e jitter. O RIPE Atlas permite que a equipe controle o alvo, as probes, a frequência e a duração das medições, além de possibilitar a atualização contínua da base. Isso torna os dados mais alinhados ao cenário que o projeto pretende monitorar e facilita a validação do modelo em medições novas. A opção exige configurar a API, acompanhar créditos e tratar eventuais dados ausentes; o PingER permanece como referência histórica para comparação e análise complementar. A escolha do RIPE Atlas já foi implementada no pipeline atual, que realiza a coleta contínua dos resultados das medições.

## 7. Estado atual (pós-decisão)

A **opção B - API do ripe Atlas** foi adotada e encontra-se operacional no pipeline atual. O **PingER permanece como referência histórica e de comparação**, não sendo a fonte utilizada para o treinamento na versão atual do projeto.
o dataset de treino é formado pelo acumulo dos resultados obtidos por meio dos "GETs" das medições do RIPE Atlas, armazenados no arquivo "curated/log_rede.csv" no bucket do projeto.

## 8. Riscos e limitações

- **PingER:** a disponibilidade dos monitores e destinos pode variar; alguns dados são agregados; há risco de respostas bloqueadas ou influenciadas pelo próprio destino; e não existe um rótulo pronto de falha.
- **Mitigação:** selecionar pares monitor-destino estáveis, documentar o período e o tamanho dos pacotes, remover períodos com dados insuficientes e definir o rótulo de falha antes do treinamento.
- **RIPE Atlas:** a disponibilidade das probes pode variar; a coleta pode consumir créditos; e as medições podem ter valores ausentes.
- **Mitigação:** começar com uma medição pequena, registrar configuração e horário de cada coleta, tratar dados ausentes, armazenar o identificador da medição e acompanhar o consumo de créditos.


## 9. Destinos atuais do hub 

Os destinos atualmente ultilizados do RIPE Atlas são:
| Papel | IP atual | Quem é | Notas |
|---|---|---|---|
| Estável | `94.140.14.14` | AdGuard DNS | Tipicamente OK |
| Estável | `208.67.222.222` | OpenDNS | Tipicamente OK |
| Caminho longo | `202.12.28.131` | APNIC | Perda ~100% → FALHA |

A intenção original utilizava os destinos `8.8.8.8`, `1.1.1.1` e `202.12.27.33`. Esses destinos foram substituídos e ficam registrados apenas como referência histórica.

A troca ocorreu devido à cota global do RIPE Atlas, que retornou HTTP 400 ao tentar utilizar `8.8.8.8`, indicando **mais de 25 medições concorrentes para o mesmo destino**. Portanto, a mudança não foi causada por falta de créditos do projeto.

## 10. Rótulo e pergunta do modelo

A pergunta canônica do modelo é classificar a condição da rede em **OK, RISCO ou FALHA**, a partir dos resultados observados em uma determinada janela de medição.

A regra de classificação adotada é:
- **FALHA:** perda de pacotes maior que 15%;
- **RISCO:** quando a perda não ultrapassa 15%, mas a latência é maior que 100 ms;
- **OK:** quando a perda não ultrapassa 15% e a latência não ultrapassa 100 ms.

No snapshot observado em 12/09/2026, o dataset apresenta aproximadamente **0% de RISCO**, enquanto as ocorrências de **FALHA estão concentradas no destino APNIC (`202.12.28.131`)**. Esse comportamento pode gerar desbalanceamento e possível viés no treinamento caso o `ip` seja utilizado como variável de entrada. A decisão sobre alteração dos destinos permanece em discussão e não deve ser realizada sem nova decisão de arquitetura.

## 11. Arquitetura de coleta 

A coleta atual é dividida em duas etapas. Primeiro, é realizado um **POST único**, utilizando 'createperiodic', para criar seis medições periódicas no RIPE atlas. Depois, os resultados são obtidos continuamente por meio de requisições **GET**, ultilizando 'fetch_measurement_results' no collector executado em AWS lamba.
o collector **não realiza um POST a cada 15 minutos**. o intervalo de 15 minutos corresponde à frequência de execução da etapa de coleta dos resultados. As medições periódicas possuem intervalo de **900 segundos**, ultilizando **2 probes no Brasil**, com medições de **ping e tracerout ICMP**. 
Os resultados coletados são ultilizados para alimentar as camadas 'raw' e curated' do dataset do projeto;

## 12. Contribuição individual

Preencher pela equipe após a divisão das atividades:

### Integrante 1 — `[Alexandre Tiago de Oliveira ]`
- **O que fez nesta etapa:** `[]`
- **Tempo dedicado (aprox.):** `[ex.: 3h30]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*:
`[]` 
`[]`

### Integrante 2 — `[Ingrid Ferreira de Sousa]`
- **O que fez nesta etapa:** `[Alterei o memorando com os dados solicitados pelo orientador e analisei a comparação entre as fontes de dados.]`
- **Tempo dedicado (aprox.):** `[ 4h ]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*:
`[Anotaçoes sobre a comparaçao:
PINGER
-tem dados dja exitentes, sem o poder de escolher quando, onde e em que frequencia pode ser feita a mediçao
-tem grandes variedades de rotas e regioes
-tem como principal finalidade achar os relatorios certos, baixando e limpando dados , nao precisa programar para coletar
os dados ja vem pronto quando baixa o relatorio.
-delimita a coleta.
RIPE ATLAS
-exige lidar com a API, gerenciando creditos e tratando os resultados que chegam de forma continua sem o trabalho de procurar dado pronto
tambem vai ter cobertura global
-a cobertura vai depender de quantos probes( voluntarios de mediçao) estao disponiveis no momento da coleta.
-tem a decisao do que vai medir detalahdamente como rede, pontos  e tempo , fazendo um teste.
-dependendo da frequencia tem um tempo maior ja que precisa criar a mediçao esperar rodar os pings e consultar o resultado
-consegue dar controle total sobre a coleta ]` 

### Integrante 3 — `[Guilherme Leite Tavares]`
- **O que fez nesta etapa:** `[]`
- **Tempo dedicado (aprox.):** `[ex.: 3h30]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*: 
`[]` 
`[]`

### Integrante 4 — `[Kauan Garcia Dias de Oliveira]`
- **O que fez nesta etapa:** `[]`
- **Tempo dedicado (aprox.):** `[ex.: 3h30]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*: 
`[]` 
`[]`

### Integrante 5 — `[Lucas Eduardo Malachias Bagatela ]`
- **O que fez nesta etapa:** `[]`
- **Tempo dedicado (aprox.):** `[ex.: 3h30]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*: 
`[]` 
`[]`

### Integrante 6 — `[Stephanie Vitoria Bessa dos Santos]`
- **O que fez nesta etapa:** `[Atualizei o memorando de decisão,incluindo a revisão da recomendação e justificativa da fonte de dados, o registro do estado atual do pipeline, a documentação dos destinos do modelo em OK, RISCO e FALHA]`
- **Tempo dedicado (aprox.):** `[3h]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*: 
`[![Evidência S1.1](evidencias/stephanie/evidencia-s1.1.png ]` 
`[]`

---


## Fontes consultadas

1. [PingER — WAN Monitoring at SLAC](https://www.slac.stanford.edu/comp/net/wan-mon.html)
2. [PingER — Tutorial, método e acesso aos dados](https://www.slac.stanford.edu/comp/net/wan-mon/tutorial.html)
3. [PingER — Métricas históricas e séries temporais](https://www.slac.stanford.edu/grp/scs/net/case/med-dec08/pinger-metrics-motion-chart-Middle_East-EDU.SLAC.STANFORD.N3-last60days.html)
4. [RIPE Atlas — Authentication](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/)
5. [RIPE Atlas — Creating Measurements](https://beta-ui.atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/)
6. [RIPE Atlas — Measurement Results](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results)
7. [RIPE Atlas — Measurement Result Format](https://atlas.ripe.net/docs/apis/measurement-result-format/)
