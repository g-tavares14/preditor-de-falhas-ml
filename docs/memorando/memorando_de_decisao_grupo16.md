# Memorando de decisão — evolução da fonte de dados

| Campo | Informação |
|---|---|
| Curso / disciplina | Estrutura de Dados II |
| Projeto integrador | Preditor de falhas ML |
| Orientador(a) | Andrea Ono Sakai |
| Data de entrega | 08/09/2026 |
| Última atualização | 26/09/2026 |
| Integrantes | Alexandre Tiago de Oliveira, Ingrid Ferreira de Sousa, Guilherme Leite Tavares, Kauan Garcia Dias de Oliveira, Lucas Eduardo Malachias Bagatela, Stephanie Vitoria Bessa dos Santos |

> Este memorando registra a avaliação inicial entre PingER e RIPE Atlas e as decisões posteriores que levaram ao uso de medições públicas do RIPE Atlas no BigQuery. A estrutura de comparação, recomendação, justificativa, riscos, contribuições e fontes segue o template da disciplina.

## 1. Situação

O projeto precisa de medições ICMP para estudar latência, perda de pacotes e jitter e analisar o comportamento de rede em rotas de regiões diferentes. A decisão começou com a comparação entre o histórico PingER e a coleta própria pela API do RIPE Atlas.

A primeira estratégia foi controlar as medições pela API do Atlas. A amostra obtida, porém, não sustentou a demonstração de treino esperada: a partição de teste ficou sem exemplos de `FALHA`, apesar de haver falhas nos dados de origem. Ao mesmo tempo, os créditos disponíveis limitaram a ampliação da coleta. Depois de avaliar também o PingER, o grupo decidiu consultar medições públicas do próprio RIPE Atlas no BigQuery e definir um recorte regional a partir das probes e dos destinos observados.

## 2. Opção A — Dataset real PingER

- **Origem / acesso:** [PingER — SLAC](https://www.slac.stanford.edu/comp/net/wan-mon.html) e [tutorial de acesso aos dados](https://www.slac.stanford.edu/comp/net/wan-mon/tutorial.html).
- **Formato:** Dados brutos de ping e relatórios resumidos disponíveis na Web; os relatórios resumidos podem ser obtidos em formato TSV compatível com planilhas.
- **Período coberto:** Há histórico público desde 1998. As medições tradicionais são feitas aproximadamente a cada 30 minutos, com séries por monitor e destino.
- **Campos disponíveis:** Monitor/origem, destino, timestamp, tamanho do pacote, pacotes enviados e recebidos, RTT mínimo/médio/máximo, perda de pacotes, indisponibilidade e jitter. Alguns relatórios também apresentam throughput derivado e métricas de qualidade.
- **Licença:** Não foi identificada uma licença aberta específica nas páginas consultadas. O uso deve manter a atribuição ao projeto PingER/SLAC e os termos de acesso devem ser confirmados antes de redistribuir os dados.

### Resumo

O PingER usa requisições e respostas ICMP Echo para medir o desempenho entre pontos de monitoramento e destinos remotos. Cada amostra registra resultados de vários pings, permitindo obter latência/RTT e perda; o jitter pode ser calculado a partir da variação dos RTTs. O histórico e a frequência aproximada de 30 minutos tornam a fonte interessante para estudar séries temporais.

O PingER foi considerado como possível complemento, mas não entrou no recorte atual. A exploração não estabeleceu uma matriz de monitores ativos e destinos compatível com os grupos regionais escolhidos, e combinar duas fontes exigiria harmonizar seus campos, frequência e pares de origem–destino. Por isso, a etapa atual mantém uma única fonte: o RIPE Atlas.

## 3. Opção B — RIPE Atlas

- **Documentação:** [Autenticação](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/), [criação de medições](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/), [resultados](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results) e [formato dos resultados](https://atlas.ripe.net/docs/apis/measurement-result-format/).
- **Origem:** Medições realizadas por probes do RIPE Atlas. O projeto considerou primeiro criar uma série própria pela API; agora consulta também medições públicas existentes no BigQuery.
- **API:** `POST /api/v2/measurements/` cria uma medição e consome créditos. `GET /api/v2/measurements/{id}/results/` lê os resultados de uma medição existente. A coleta periódica própria foi desenhada para fazer o POST na configuração e usar apenas GET nas execuções recorrentes.
- **BigQuery:** A consulta atual lê `ripencc-atlas.measurements.ping`, filtra registros IPv4 e restringe probes, destinos e período. A extração atual usa uma janela móvel de sete dias.
- **Resultado:** A tabela oferece os registros brutos de ping; métricas de trabalho e rótulos são preparados posteriormente em Python.

### Resumo

A API do RIPE Atlas permite controlar probes, alvos, intervalo e duração, mas ampliar a coleta própria depende da disponibilidade de créditos e de tempo para acumular medições. O BigQuery oferece acesso a medições públicas já existentes da mesma fonte, sem criar novas medições Atlas. Isso permite ampliar a exploração sem misturar, nesta etapa, dados de provedores diferentes.

## 4. Comparação

| Critério | PingER | RIPE Atlas — API própria | RIPE Atlas — BigQuery |
|---|---|---|---|
| Fonte | Monitores e destinos PingER | Probes e medições criadas pelo grupo | Medições públicas do RIPE Atlas |
| Controle da coleta | Baixo: dados já coletados | Alto: o grupo configura alvos, probes e intervalo | Não cria medições; seleciona registros públicos existentes |
| Cobertura regional | Depende dos monitores e destinos disponíveis | Depende das probes selecionadas e da execução | Depende das combinações probe–destino presentes na tabela |
| Tempo até obter dados | Rápido após selecionar e baixar relatórios | Exige configurar a medição e esperar resultados | Consulta o histórico disponível na tabela |
| Créditos Atlas | Não usa créditos Atlas | POST consome créditos | Não exige novos POSTs no Atlas |
| Adaptação ao recorte atual | Exigiria harmonização com a fonte Atlas | Compatível com o ecossistema do projeto, mas a série coletada foi insuficiente para a evidência desejada | Usa a mesma fonte e permite filtrar probes, destinos e janela regional |

## 5. Recomendação

Para o recorte de dados analisado atualmente, recomenda-se usar **medições públicas do RIPE Atlas no BigQuery** como fonte bruta. O PingER fica documentado como alternativa histórica, mas não será misturado à extração atual. A API do Atlas permanece como parte da trajetória do projeto e permite coleta controlada, mas não é a origem da consulta regional descrita neste memorando.

## 6. Justificativa

A escolha evoluiu a partir dos resultados do próprio trabalho. A coleta controlada pela API era adequada para definir alvos e intervalos, mas a quantidade de dados disponível não produziu uma partição de teste com casos de `FALHA`; a limitação de créditos também impediu ampliar a série como planejado. O grupo precisava de mais observações para preparar os dados e avaliar o modelo, sem afirmar antecipadamente que a predição estaria garantida.

O PingER foi pesquisado por oferecer histórico longo e medições ICMP, mas encontrar monitores e destinos compatíveis com o recorte regional e harmonizar uma segunda fonte acrescentaria outra etapa de validação. O BigQuery foi escolhido porque disponibiliza medições públicas da mesma fonte RIPE Atlas e permite consultar os campos de ping por probe, destino e tempo.

A análise atual organiza as rotas por região de destino. Essa informação ajuda a comparar caminhos nacionais e intercontinentais, cujas latências esperadas diferem. O BigQuery fornece os dados brutos e os metadados regionais selecionados; a preparação das métricas e a criação de rótulos ficam para Python. A escolha da fonte amplia o material disponível para análise, mas não é, isoladamente, evidência de que o modelo fará previsões corretas.

## 7. Riscos e limitações

- **PingER:** a disponibilidade de monitores e destinos varia; os campos e a cadência podem diferir dos registros Atlas; não há rótulo pronto de falha.
- **Mitigação:** manter PingER fora da extração atual. Antes de incorporá-lo, verificar pares ativos, compatibilidade de campos e regras para alinhar as séries.
- **RIPE Atlas API:** a disponibilidade das probes varia, a criação consome créditos e a série própria foi insuficiente para a demonstração de treino esperada.
- **Mitigação:** manter separados o setup via POST e a leitura via GET; acompanhar créditos e não tratar uma medição pontual como série temporal.
- **RIPE Atlas BigQuery:** a consulta não garante que cada probe tenha medido todos os destinos; a existência de uma linha recente comprova atividade no período consultado, não conexão neste instante. Sete dias podem ainda ser insuficientes para algumas regiões ou classes.
- **Mitigação:** medir a quantidade e distribuição temporal dos registros por grupo antes do treino, preservar a extração bruta e documentar o período consultado. Não preencher combinações ausentes com dados inventados.
- **Âncoras regionais:** país e região são associados aos IPs selecionados para este recorte; a consulta não deduz a localização automaticamente.
- **Mitigação:** manter a lista de endereços e sua classificação documentadas e revisar a cobertura efetivamente encontrada antes de interpretar resultados regionais.
- **Rótulos:** a consulta BigQuery não calcula `status_real` nem transforma, por si só, os dados em evidência de predição.
- **Mitigação:** derivar as métricas em Python (seção 9). A regra de rótulo está pendente de decisão; quando for definida, registrar a regra usada e avaliar a distribuição das classes antes do treino.

## 8. Contribuição individual

Os registros abaixo correspondem às contribuições documentadas na elaboração inicial deste memorando. Os campos vazios continuam disponíveis para complementação pelos respectivos integrantes.

Distribuição das contribuições nesta etapa:

### Integrante 1 — `Alexandre Tiago de Oliveira`
- **O que fez nesta etapa:** `[]`
- **Tempo dedicado (aprox.):** `[ex.: 3h30]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*:
`[]` 
`[]`

### Integrante 2 — `Ingrid Ferreira de Sousa`
- **O que fez nesta etapa:** `[Realizei o preenchimento do memorando e organizei as informações fornecidas pela equipe.]`
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

### Integrante 3 — `Guilherme Leite Tavares`
- **O que fez nesta etapa:** `[Realizei a pesquisa do banco de dados e levantei as informações sobre as fontes de dados analisadas.]`
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
- **O que fez nesta etapa:** `[]`
- **Tempo dedicado (aprox.):** `[ex.: 3h30]`
- **Evidência da contribuição** *(print de conversa, rascunho, e-mail, documento compartilhado etc.)*: 
`[]` 
`[]`

---

## 9. Atualização da decisão — recorte regional no BigQuery

A decisão sobre a fonte mudou conforme o grupo observou os limites da coleta própria e explorou o histórico público. A sequência foi:

1. Comparar o dataset histórico PingER com a coleta pela API do RIPE Atlas.
2. Começar pelo RIPE Atlas para ter controle sobre probes, destinos e frequência; medições pontuais serviram para testar a configuração, mas não formaram histórico suficiente.
3. Tentar ampliar a série própria. A primeira matriz considerava `8.8.8.8`, `1.1.1.1` e `202.12.27.33`, mas a tentativa esbarrou no limite de medições concorrentes. O desenho foi revisto para uma série periódica com quatro destinos: `94.140.14.14` (AdGuard DNS), `208.67.222.222` (OpenDNS), `202.12.28.131` (APNIC) e `4.2.2.1` (Level3/Lumen). Essa matriz pertencia à coleta ativa pela API e é diferente das seis âncoras da extração BigQuery atual.
4. Avaliar o primeiro treino e observar que a partição de teste não continha casos de `FALHA`, apesar de haver falhas nos dados de origem.
5. Buscar mais medições sem depender de novos créditos e decidir usar a tabela pública do RIPE Atlas no BigQuery. PingER não foi combinado ao conjunto atual.
6. Explorar probes brasileiras e destinos registrados nas medições, selecionar 13 IDs de origem e seis âncoras conhecidas e organizar a extração por quatro grupos regionais.

| Item | Decisão atual |
|---|---|
| Fonte e tabela | RIPE Atlas BigQuery — extração em `ripencc-atlas.measurements.ping` |
| Tabela lida pelo pipeline | `atlas-ripe-509700.atlasRipe.atlas` (região EU), lida por `src/preditor` em PySpark; cobre 18/09 a 25/09/2026 |
| Janela da consulta | Sete dias anteriores ao momento da execução |
| Origem | 13 probes selecionadas no Brasil: `6349`, `6410`, `6602`, `6659`, `6790`, `6891`, `6977`, `7019`, `7113`, `7242`, `7307`, `7508` e `7708` |
| Destinos | Brasil (`150.164.1.222`); Miami, EUA (`92.38.132.60`); Portugal (`91.209.16.127`); Alemanha (`129.143.66.65`); Singapura (`202.6.102.41`); Japão (`133.69.15.4`) |
| Grupos regionais | `BR → BR`, `BR → América do Norte`, `BR → Europa` e `BR → Ásia` |
| Saída da consulta | Medições brutas de ping IPv4 observadas para os filtros; não há rótulo calculado no SQL |
| Baseline | Por fluxo (`prb_id`, destino e medição do Atlas), calculada só no Período A — as primeiras 108 h da tabela |
| Features (X) | Métricas relativas à baseline de cada fluxo, calculadas no Período B: `latencia_relativa`, `aumento_pct`, `z_robusto`, `jitter_relativo` e, sobre as últimas cinco medições do fluxo, `n5_timeout`, `n5_aumento80`, `n5_moderado`, `tendencia` e `persistencia`. País e região são metadados, não features |
| Rótulo (Y) | Pendente de decisão (tratamento de fluxos com MAD baixo). Nenhuma regra fixa de rótulo está vigente nesta etapa |

As features relativas substituem o conjunto `curated/features.csv` + `curated/labels.csv` da primeira fase, que passa a ser legado. O rótulo por limiar fixo usado na primeira fase (notebook `03`) também não é aplicado por padrão ao recorte atual.

A coleta ativa pela API do Atlas (primeira fase, com os quatro destinos citados no passo 3) é histórica: fica documentada pelos notebooks `01` (GET) e `02` (POST) e não é a fonte do dataset atual.

A lista inicial de 433 probes públicas brasileiras não foi tratada como 433 probes ativas. O recorte final usa os 13 IDs selecionados e a consulta retorna somente combinações com registros correspondentes na tabela. A seleção de seis destinos também não significa que cada probe tenha consultado todos eles. A consulta é uma fotografia de uma janela histórica; não verifica o estado de conexão ao vivo.

As consultas e a explicação passo a passo estão em [`../data/docs/query.md`](../data/docs/query.md). A história da mudança de fonte está em [`../data/docs/dataset-fonte-atlas.md`](../data/docs/dataset-fonte-atlas.md), e a lista dos IDs e destinos está em [`../data/README.md`](../data/README.md).

---

## Fontes consultadas

1. [PingER — WAN Monitoring at SLAC](https://www.slac.stanford.edu/comp/net/wan-mon.html)
2. [PingER — Tutorial, método e acesso aos dados](https://www.slac.stanford.edu/comp/net/wan-mon/tutorial.html)
3. [PingER — Métricas históricas e séries temporais](https://www.slac.stanford.edu/grp/scs/net/case/med-dec08/pinger-metrics-motion-chart-Middle_East-EDU.SLAC.STANFORD.N3-last60days.html)
4. [RIPE Atlas — Authentication](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/)
5. [RIPE Atlas — Creating Measurements](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/)
6. [RIPE Atlas — Measurement Results](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results)
7. [RIPE Atlas — Measurement Result Format](https://atlas.ripe.net/docs/apis/measurement-result-format/)
8. [RIPE NCC — repositório de documentação do BigQuery Atlas](https://github.com/RIPE-NCC/ripe-atlas-bigquery)
9. [Consultas BigQuery e histórico do recorte regional](../data/docs/query.md)
10. [Evolução da fonte de dados](../data/docs/dataset-fonte-atlas.md)
11. [README dos dados, probes e destinos selecionados](../data/README.md)
12. [Guia de coleta RIPE Atlas enviado pela professora](../projeto_preditor_redes/Guia_Coleta_RIPE_Atlas.md)
13. [RFC do projeto acadêmico](../projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md)
