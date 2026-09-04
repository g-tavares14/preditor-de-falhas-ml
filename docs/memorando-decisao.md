# Memorando de decisão — Fonte de dados

| Campo | Informação |
|---|---|
| Curso / disciplina | Não informado |
| Projeto integrador | Preditor de falhas ML |
| Orientador(a) | A confirmar |
| Data de entrega | A confirmar |
| Integrantes | A confirmar pela equipe |

> Este documento usa como base a pesquisa sobre o PingER, a documentação oficial do RIPE Atlas e as instruções do template do memorando.

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

Para a primeira versão do pipeline, recomenda-se a **Opção B — API do RIPE Atlas**, mantendo o PingER como referência histórica e possível fonte complementar.

## 6. Justificativa

O objetivo atual exige dados temporais de latência, perda de pacotes e jitter. O RIPE Atlas permite que a equipe controle o alvo, as probes, a frequência e a duração das medições, além de possibilitar a atualização contínua da base. Isso torna os dados mais alinhados ao cenário que o projeto pretende monitorar e facilita a validação do modelo em medições novas. A opção exige configurar a API, acompanhar créditos e tratar eventuais dados ausentes; o PingER permanece como referência histórica para comparação e análise complementar.

## 7. Riscos e limitações

- **PingER:** a disponibilidade dos monitores e destinos pode variar; alguns dados são agregados; há risco de respostas bloqueadas ou influenciadas pelo próprio destino; e não existe um rótulo pronto de falha.
- **Mitigação:** selecionar pares monitor-destino estáveis, documentar o período e o tamanho dos pacotes, remover períodos com dados insuficientes e definir o rótulo de falha antes do treinamento.
- **RIPE Atlas:** a disponibilidade das probes pode variar; a coleta pode consumir créditos; e as medições podem ter valores ausentes.
- **Mitigação:** começar com uma medição pequena, registrar configuração e horário de cada coleta, tratar dados ausentes, armazenar o identificador da medição e acompanhar o consumo de créditos.

## 8. Contribuição individual

Preencher pela equipe após a divisão das atividades:

| Integrante | Atividade realizada | Tempo aproximado | Evidência |
|---|---|---|---|
| Integrante 1 | A confirmar | A confirmar | A confirmar |
| Integrante 2 | A confirmar | A confirmar | A confirmar |
| Integrante 3 | A confirmar | A confirmar | A confirmar |
| Integrante 4 | A confirmar | A confirmar | A confirmar |
| Integrante 5 | A confirmar | A confirmar | A confirmar |
| Integrante 6 | A confirmar | A confirmar | A confirmar |

## Fontes consultadas

1. [PingER — WAN Monitoring at SLAC](https://www.slac.stanford.edu/comp/net/wan-mon.html)
2. [PingER — Tutorial, método e acesso aos dados](https://www.slac.stanford.edu/comp/net/wan-mon/tutorial.html)
3. [PingER — Métricas históricas e séries temporais](https://www.slac.stanford.edu/grp/scs/net/case/med-dec08/pinger-metrics-motion-chart-Middle_East-EDU.SLAC.STANFORD.N3-last60days.html)
4. [RIPE Atlas — Authentication](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/)
5. [RIPE Atlas — Creating Measurements](https://beta-ui.atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/)
6. [RIPE Atlas — Measurement Results](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results)
7. [RIPE Atlas — Measurement Result Format](https://atlas.ripe.net/docs/apis/measurement-result-format/)
