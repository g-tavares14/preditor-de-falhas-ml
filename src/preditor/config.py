"""Parâmetros do projeto. Tudo que é "número mágico" fica aqui, com a origem."""

from pathlib import Path

# --- Fonte dos dados (BigQuery) ---------------------------------------------
PROJECT = "atlas-ripe-509700"
TABLE = f"{PROJECT}.atlasRipe.atlas"
LOCATION = "EU"
ORIGEM = "BR"  # todas as probes do recorte são brasileiras (data/README.md)

# --- Divisão temporal --------------------------------------------------------
# Período A = primeiras 108 h da tabela: serve só para calcular o "normal"
# (baseline) de cada fluxo. Período B = o restante: é onde o modelo trabalha.
# 108 h é o menor corte em que todos os fluxos passam do piso abaixo.
HORAS_PERIODO_A = 108

# RFC §8.2: sem 1.500 RTT válidos no Período A, o fluxo não tem baseline.
PISO_RTT_VALIDOS = 1500

# --- Estatística robusta -----------------------------------------------------
# Multiplicar o MAD por 1,4826 o coloca na mesma escala de um desvio-padrão.
FATOR_MAD = 1.4826
# Substituto quando MAD = 0 (RFC §8.4): IQR / 1,349, com piso de 1 ms.
FATOR_IQR = 1.349
ESCALA_MINIMA_MS = 1.0

# --- Limiares da regra de rótulo (RFC §8.4) ----------------------------------
Z_RISCO = 2.0  # z robusto a partir do qual o desvio é "moderado"
Z_FALHA = 3.5  # z robusto a partir do qual o desvio é "extremo"
AUMENTO_RISCO_PCT = 30  # aumento do RTT sobre a mediana
AUMENTO_FALHA_PCT = 80
# Piso da linha 3 (decisão do dono, 09/10/2026, SPEC-piso-regra3.md): z extremo só vira FALHA se o RTT também subiu
# pelo menos este % sobre a mediana. Sem ele, um MAD de décimos de ms faz 1 ms virar z >= 3,5 (88 % das FALHAs da
# regra 3 tinham aumento < 30 %). O valor é o limite de RISCO da própria tabela (AUMENTO_RISCO_PCT), não um número
# escolhido na validação. None = a regra 3 da RFC ao pé da letra (reversão).
PISO_AUMENTO_FALHA_PCT = AUMENTO_RISCO_PCT
JITTER_RISCO = 3.0  # jitter atual / jitter típico
JANELA = 5  # quantas medições recentes olhamos (a atual + 4 anteriores)
# Linhas 1, 2, 4 e 5 da tabela de rótulo (a linha 3 usa Z_FALHA e o piso, acima).
PERDA_FALHA_PCT = 10  # perda_pct a partir do qual a medição é FALHA (linha 1)
N5_TIMEOUT_FALHA = 3  # timeouts nas últimas 5 medições para ser FALHA (linha 2)
N5_AUMENTO80_FALHA = 2  # medições com aumento > 80 % nas últimas 5 para ser FALHA (linha 4)
N5_RISCO = 2  # desvios moderados nas últimas 5 para ser RISCO (linha 5, `n5_risco` da RFC)

# --- Rótulo futuro (RFC §3 + decisão de SPEC-calculo-y.md, "status_futuro") ------
# O preditor olha 12 min à frente: 3 medições × 240 s (intervalo do Atlas). Se houve lacuna
# na coleta, a 3ª medição seguinte não é "12 minutos depois": fora de 10 a 14 min vira nulo.
PASSOS_FUTURO = 3  # quantas medições à frente do mesmo fluxo
FUTURO_MIN_S = 600  # 10 min, limite inclusivo
FUTURO_MAX_S = 840  # 14 min, limite inclusivo

# --- Recorte temporal em blocos (Tarefa 2, seção 5, e RFC §9) ----------------------
# Dois instantes de corte, iguais para todos os fluxos, medidos da primeira à última medição
# rotulada: treino = primeiros 50 %, validação = os 20 % seguintes, teste = o restante (30 %).
# Sem sorteio de linhas: embaralhar misturaria o futuro no treino (RFC §9).
FRACAO_TREINO = 0.5
FRACAO_VALIDACAO = 0.2

# --- Exemplos para o diário da Tarefa 2 (decisão do dono, 01/10/2026) -------------------------
# Só escolhem QUAIS linhas são impressas como exemplo; não entram no rótulo nem no modelo.
# O exemplo OK de "caminho longo" é a linha OK de maior RTT entre as de z baixo. "z baixo" =
# |z_robusto| <= 1, metade do limiar de RISCO (Z_RISCO = 2): a medição está bem dentro do normal da rota.
EXEMPLO_OK_Z_MAX = 1.0
# O exemplo FALHA usa z com folga sobre o limiar (Z_FALHA = 3,5), para que a conferência à mão,
# com mediana e MAD arredondados, não caia do outro lado do limiar.
EXEMPLO_FALHA_Z_MIN = 5.0

# --- Camadas de dados (arquitetura medalhão, SPEC-medalhao.md) ------------------
DADOS = Path(__file__).resolve().parents[2] / "data"
BRONZE = DADOS / "bronze"  # cópia fiel da tabela do BigQuery, sem filtro nem cálculo
ARQUIVO_BRONZE = BRONZE / "atlas.parquet"  # a tabela inteira, com `pings` aninhado
SILVER = DADOS / "silver"  # uma linha por medição, já normalizada
ARQUIVO_SILVER = SILVER / "medicoes.parquet"  # saída de `silver/medicao.py`
GOLD = DADOS / "gold"  # baseline, features e rótulo: o que o modelo consome
ARQUIVO_BASELINE = GOLD / "baseline_por_fluxo.parquet"  # a "ficha" de cada fluxo (Período A)
ARQUIVO_FEATURES = GOLD / "features_B.parquet"  # o X do modelo (Período B)
ARQUIVO_ROTULADO = GOLD / "dataset_rotulado_B.parquet"  # features + rótulo (saída de `gold/calculo_y/`)
ARQUIVO_LIMITES = GOLD / "limites_por_regiao.csv"  # relatório para leitura humana
ARQUIVO_CONTAGEM = GOLD / "contagem_classes.csv"  # bloco × classe e instantes de corte (leitura humana)
MODELO = DADOS / "modelo"  # saídas da árvore (`modelo/execucao.py`): busca, regras, métricas

# Checagem do Silver: fluxos distintos nas medições = os 81 do baseline + 1 fluxo
# que só tem medições no Período B (7708|92.38.132.60|214331389). Decisão de
# AGENTS.md, conferida no dataset de 7 dias (tasks/todo.md, "Números de referência"). Continua
# valendo depois da remoção de duplicatas do Silver (tasks/todo-calculo-y.md, "Números de referência").
FLUXOS_SILVER = 82

# Checagem do Gold: o baseline tem uma linha por fluxo com medições no Período A (81), e
# 2 deles não chegam a 1.500 RTT válidos (`baseline_insuficiente`). Decisão de AGENTS.md,
# conferida no dataset de 7 dias (tasks/todo.md, "Números de referência") e depois da remoção
# de duplicatas (tasks/todo-calculo-y.md, "Números de referência").
FLUXOS_BASELINE = 81
FLUXOS_INSUFICIENTES = 2

# --- Árvore de decisão (SPEC-arvore.md; diário da Tarefa 3) ---------------------------------
# Diário da Tarefa 3, seção 1: só métricas relativas ao baseline do fluxo, nunca valores absolutos.
# `n5_moderado` é o `n5_risco` do diário (mesma equivalência de SPEC-calculo-y.md).
COLUNAS_ARVORE = [
    "z_robusto",
    "aumento_pct",
    "jitter_relativo",
    "perda_pct",
    "timeout_atual",
    "n5_timeout",
    "n5_aumento80",
    "n5_moderado",
]

# SPEC-ajuste-arvore.md, "Colunas novas" (Tarefa 4): o histórico do `z_robusto` nas últimas `JANELA` medições.
# Nascem no Gold (`gold/calculo_x/features.py`), mas só a árvore ajustada as vê: a da Tarefa 3 segue com as 8 acima.
COLUNAS_AJUSTE = ["min5_z", "media5_z"]
# Diferença aceita ao conferir essas duas colunas por outro caminho no Gold: a média somada em outra ordem
# muda as últimas casas do float (decisão: bem abaixo de qualquer limiar que a árvore use).
TOLERANCIA_JANELA = 1e-9

# SPEC-arvore.md, "Colunas da árvore oficial": existem no dataset rotulado, mas nunca entram no X.
# Identificam o fluxo (`fluxo_id`, IP, `rota`), são metadados que a RFC proíbe (país, região), dão o
# valor absoluto (`rtt`, `jitter`), vazam a resposta (`status_atual`, `regra`, `status_futuro`) ou só
# organizam os dados (`t`, `periodo`, `bloco`). As cinco últimas (`latencia_relativa` a `desviado`)
# não estão na lista do diário: a Tarefa 4 pode discutir incluí-las.
COLUNAS_PROIBIDAS = [
    "fluxo_id", "prb_id", "dst_addr", "msm_id", "rota",
    "destination_country", "destination_region",
    "rtt", "jitter", "t", "periodo", "bloco",
    "status_atual", "regra", "status_futuro",
    "latencia_relativa", "tendencia", "persistencia", "moderado", "desviado",
]

# Decisão do dono, 01/10/2026: a árvore oficial é o preditor, então o alvo é o rótulo 12 min à frente.
ALVO = "status_futuro"
CLASSES = ("OK", "RISCO", "FALHA")  # ordem fixa das matrizes e métricas (Tarefa 3, seção 3)
# Mesmos nomes (e ordem de tempo) de `gold/calculo_y/recorte.py`; o `fit` só vê o treino e a escolha
# usa a validação. O teste só aparece como N até a Tarefa 5.
BLOCO_TREINO = "treino"
BLOCO_VALIDACAO = "validacao"
BLOCO_TESTE = "teste"

# Matriz e métricas na validação (SPEC-arvore.md, "Leitura do erro"). Um arquivo para todos os modelos:
# cada um entra com o nome na coluna `modelo` (persistência, árvore oficial e contraste).
ARQUIVO_MATRIZ = MODELO / "matriz_validacao.csv"
ARQUIVO_METRICAS = MODELO / "metricas_validacao.csv"
MODELO_PERSISTENCIA = "persistencia"  # a régua de comparação: "o futuro é igual ao `status_atual`" (RFC §9)
CASAS_CSV = 6  # casas decimais das métricas nos CSVs (decisão: o suficiente para conferir à mão)
TOLERANCIA_METRICA = 1e-9  # diferença aceita entre a métrica do scikit-learn e a recalculada da matriz

# --- Árvore oficial (SPEC-arvore.md, "Como a árvore é escolhida"; diário da Tarefa 3, seção 2) ----------
CRITERIO = "gini"  # critério de divisão do CART pedido pelo diário
SEMENTE = 16  # número do grupo: com ela fixa, o treino refaz sempre a mesma árvore
# Grade da busca: 7 × 4 = 28 árvores, todas treinadas só no treino e medidas na validação.
# Sem `class_weight`: decisão do dono (01/10/2026); o balanceamento fica para a Tarefa 4.
GRADE_PROFUNDIDADE = [2, 3, 4, 5, 6, 8, 10]  # `max_depth`
GRADE_FOLHA_MINIMA = [50, 100, 200, 500]  # `min_samples_leaf`
NIVEIS_DIVISOES = 2  # quantos níveis de divisões a saída mostra (diário, seção 2: "os dois primeiros")

# Saídas da árvore oficial em `data/modelo/`. As métricas dela entram nos CSVs de matriz e métricas
# (acima), ao lado da persistência, com este nome na coluna `modelo`.
MODELO_ARVORE = "arvore_oficial"
ARQUIVO_BUSCA = MODELO / "busca_hiperparametros.csv"  # as 28 combinações; a primeira linha é a escolhida
ARQUIVO_ARVORE = MODELO / "arvore_oficial.json"  # critério, hiperparâmetros, profundidade, folhas, semente, colunas
ARQUIVO_REGRAS = MODELO / "regras_arvore_oficial.txt"  # `export_text` com o nome das colunas + as regras em português

# Regras em português (SPEC-arvore.md, "Como a árvore é escolhida"; diário da Tarefa 3, seção 2).
N_REGRAS_PORTUGUES = 3  # as 3 folhas com mais linhas de treino, uma por classe quando existir
# Casas decimais do limiar na regra impressa. 2 casas (como o `export_text`) podem arredondar demais e
# passar a descrever outro conjunto de linhas; a checagem usa o limiar exato da árvore e confere também que
# o texto arredondado, lido como está, seleciona as mesmas linhas (decisão da A4: com 2 casas a regra impressa
# seleciona linhas diferentes; 4 passam na checagem).
CASAS_LIMIAR_REGRA = 4

# Erros concretos da validação (SPEC-arvore.md, "Leitura do erro"). Estas colunas só LOCALIZAM a linha
# (`fluxo_id`, `t`) e dão o valor absoluto dela (`rtt`): estão em COLUNAS_PROIBIDAS e nunca entram no X.
# A mediana do baseline do fluxo (de ARQUIVO_BASELINE) também só classifica o caminho em longo ou curto.
COLUNAS_LOCALIZACAO = ["fluxo_id", "t", "rtt"]
COLUNA_MEDIANA_FLUXO = "mediana_fluxo"  # `mediana` de baseline_por_fluxo.parquet, trazida para a linha da validação

# --- Árvore de contraste (SPEC-arvore.md, "Árvore de contraste"; diário da Tarefa 3, seção 4) --------
# Colunas extras de ORIGEM da árvore de contraste (diário, seção 4 + decisão do dono, 01/10/2026): o RTT absoluto
# em ms e a região de destino. Ambas estão em COLUNAS_PROIBIDAS: só esta árvore as vê, e ela não é o modelo do projeto.
# `destination_region` vira uma coluna 0/1 por região (nome: PREFIXO_REGIAO + a região); as regiões são as do treino.
COLUNA_RTT_CONTRASTE = "rtt"  # a coluna numérica extra: o RTT da medição, em ms (ausente fica ausente)
COLUNA_REGIAO_CONTRASTE = "destination_region"  # a coluna categórica extra, que vira uma coluna 0/1 por região
COLUNAS_CONTRASTE = [COLUNA_RTT_CONTRASTE, COLUNA_REGIAO_CONTRASTE]
PREFIXO_REGIAO = COLUNA_REGIAO_CONTRASTE + "_"
MODELO_CONTRASTE = "arvore_contraste"  # nome na coluna `modelo` dos CSVs de matriz e métricas
# Só o `export_text`: a árvore de contraste não vira modelo (sem JSON de parâmetros e sem regras em português).
ARQUIVO_REGRAS_CONTRASTE = MODELO / "regras_arvore_contraste.txt"

# --- Árvore ajustada (SPEC-ajuste-arvore.md; diário da Tarefa 4) ----------------------------------------
# A árvore da Tarefa 3 (acima) não muda: a ajustada nasce ao lado, no comando `ajuste`, e é medida contra ela.
# Grade: a mesma de profundidade e folha da Tarefa 3, vezes o critério (o diário permite Gini ou entropia):
# 7 × 4 × 2 = 56 árvores por variante de peso.
GRADE_CRITERIO_AJUSTE = ["gini", "entropy"]  # a ordem é a do desempate: no empate, vence o primeiro (Gini)
# Peso de classe no `fit` (decisão do dono, 02/10/2026; docs/relatorio_analise_arvore.md, seção 3.3: o peso com a
# melhor média entre os testados). O diário da Tarefa 4 não lista peso entre os ajustes permitidos: a pergunta vai
# à professora na revisão. Por isso a busca roda nas duas variantes e as duas são gravadas.
PESO_CLASSES_AJUSTE = {"OK": 1.0, "RISCO": 2.0, "FALHA": 1.5}
MODELO_AJUSTE_SEM_PESO = "ajustada_sem_peso"  # nomes na coluna `modelo` dos CSVs do ajuste
MODELO_AJUSTE_COM_PESO = "ajustada_com_peso"
VARIANTES_AJUSTE = {MODELO_AJUSTE_SEM_PESO: None, MODELO_AJUSTE_COM_PESO: PESO_CLASSES_AJUSTE}
# Qual variante é "a árvore ajustada" (a que tem JSON e regras em português). Se a professora vetar o peso,
# troca-se só esta linha para MODELO_AJUSTE_SEM_PESO.
MODELO_AJUSTADA = MODELO_AJUSTE_COM_PESO
# Regra de escolha (decisão do dono, 02/10/2026): entre as árvores com F1 macro da validação a até esta distância
# do melhor, vence a mais simples (menor `max_depth`, depois `min_samples_leaf` maior, depois Gini). O maior F1
# puro levaria a 187 folhas por +0,004, e diferenças abaixo de 0,007 estão dentro do ruído (relatório, seção 4).
TOLERANCIA_ESCOLHA = 0.005
# Casas do limiar nas regras em português da ajustada. As 4 da Tarefa 3 (`CASAS_LIMIAR_REGRA`) não bastam aqui: com
# 4, o limiar impresso seleciona linhas diferentes das da folha e a checagem de `Regras.verificar` para (A6).
# É o menor número que passa nessa checagem; o texto das regras da Tarefa 3 continua com 4.
CASAS_LIMIAR_REGRA_AJUSTE = 6

# Saídas do `ajuste` em `data/modelo/`. Arquivos próprios: os da Tarefa 3 não são reescritos (o `replay` os confere).
ARQUIVO_BUSCA_AJUSTE = MODELO / "busca_ajuste.csv"  # as 56 combinações de cada variante, com a escolhida marcada
ARQUIVO_ARVORE_AJUSTADA = MODELO / "arvore_ajustada.json"  # critério, hiperparâmetros, folhas, semente, peso, colunas
ARQUIVO_REGRAS_AJUSTADA = MODELO / "regras_arvore_ajustada.txt"  # `export_text` + as regras em português
ARQUIVO_MATRIZ_AJUSTE = MODELO / "matriz_ajuste.csv"  # matriz 3×3 de persistência, Tarefa 3 e as duas variantes
ARQUIVO_METRICAS_AJUSTE = MODELO / "metricas_ajuste.csv"  # as métricas de sempre + futuro muda, transições e regiões
ARQUIVO_COMPARACAO = MODELO / "comparacao_t3_t4.csv"  # a tabela do diário: F1 macro, recall de FALHA e de RISCO

# --- Comparação de modelos: Random Forest e XGBoost (SPEC-comparacao-modelos.md; tasks/plan-comparacao-modelos.md) ---
# As duas famílias usam o mesmo X da árvore ajustada (10 colunas), o mesmo peso de classe (o da ajustada adotada, em
# `floresta.py` e `boosting.py`) e a mesma semente. As grades abaixo são PROPOSTAS do plano (10/10/2026): o tempo de
# treino confirma: M2 (10/10/2026) 32 florestas em ~3 a 3,5 min; M3, 16 modelos XGBoost em ~22 s. Nenhuma grade passou
# de ~10 min, então nenhuma foi reduzida (parada obrigatória do todo: tasks/todo-comparacao-modelos.md).
# Saídas em `data/modelo/comparacao/` (ignorada pelo git): a escrita é do comando `comparar`.
COMPARACAO = MODELO / "comparacao"
MODELO_FLORESTA = "random_forest"  # nome na coluna `modelo` dos CSVs da comparação
# Random Forest: 2 × 4 × 4 = 32 florestas, todas treinadas só no treino e medidas na validação.
GRADE_ARVORES_FLORESTA = [100, 300]  # `n_estimators` (nº de árvores): proposta do plano
GRADE_PROFUNDIDADE_FLORESTA = [4, 6, 8, 12]  # `max_depth`: proposta do plano, um pouco mais ampla que a da árvore (2 a 10)
GRADE_FOLHA_MINIMA_FLORESTA = [20, 50, 100, 200]  # `min_samples_leaf`: proposta do plano; folha menor que a árvore (50 a 500)
# `sqrt` = raiz de 10 colunas, ~3 por divisão: o padrão do scikit-learn para classificação, pedido no plano.
MAX_FEATURES_FLORESTA = "sqrt"
ARQUIVO_BUSCA_FLORESTA = COMPARACAO / "busca_floresta.csv"  # as 32 florestas, com a escolhida marcada (escrito pelo `comparar`)
MODELO_BOOSTING = "xgboost"  # nome na coluna `modelo` dos CSVs da comparação
# XGBoost: 2 × 2 × 4 = 16 modelos. Cada rodada de boosting são 3 árvores (uma por classe), então 300 rodadas = 900 árvores.
GRADE_ARVORES_BOOSTING = [100, 300]  # `n_estimators` (rodadas): proposta do plano
GRADE_TAXA_APRENDIZADO_BOOSTING = [0.05, 0.1]  # `learning_rate` (passo de cada rodada): proposta do plano
GRADE_PROFUNDIDADE_BOOSTING = [2, 3, 4, 6]  # `max_depth`: proposta do plano
# `hist` = divisões por histograma, o método rápido e padrão do XGBoost moderno; pedido no plano.
TREE_METHOD_BOOSTING = "hist"
# Sem parada antecipada (`early_stopping_rounds`): ela olharia a validação para decidir o treino (SPEC-comparacao-modelos.md).
ARQUIVO_BUSCA_BOOSTING = COMPARACAO / "busca_boosting.csv"  # as 16 combinações, com a escolhida marcada (escrito pelo `comparar`)

# Regra de escolha ENTRE famílias (SPEC-comparacao-modelos.md, "Regra de escolha", item 2): a mesma regra da Tarefa 4
# (a até TOLERANCIA_ESCOLHA do maior F1 macro da validação), e entre as que sobram vence a mais simples. A ordem
# abaixo é a de simplicidade da spec. A persistência e a árvore da Tarefa 3 são só referência: não concorrem.
ORDEM_FAMILIAS = [MODELO_AJUSTADA, MODELO_FLORESTA, MODELO_BOOSTING]
# IC pareado por fluxo (SPEC-comparacao-modelos.md, "Estrutura" e "Regra de escolha", item 2): 2.000 reamostras e
# nível de 95 %, pedidos na spec; a semente é a SEMENTE do projeto. O IC é gravado e dito no relatório, mas não decide.
IC_REAMOSTRAS = 2000
IC_NIVEL = 0.95
# Tempo de previsão: a mediana de 3 medições na validação (decisão desta execução: uma medição só varia com a carga
# da máquina). Só vai para `tempos.csv`, que a checagem de "mesma execução = mesmos arquivos" não compara.
REPETICOES_PREVISAO = 3
# Saídas da comparação em `data/modelo/comparacao/` (todas, menos `tempos.csv`, iguais em duas execuções).
ARQUIVO_COMPARACAO_MODELOS = COMPARACAO / "comparacao_modelos.csv"  # as 5 linhas: métricas, transições, tamanho
ARQUIVO_MATRIZ_COMPARACAO = COMPARACAO / "matriz_comparacao.csv"  # matriz 3×3 das 5 linhas
ARQUIVO_IC_PAREADO = COMPARACAO / "ic_pareado.csv"  # IC 95 % da diferença de F1 macro por fluxo (não decide)
ARQUIVO_ESCOLHA = COMPARACAO / "escolha.json"  # o modelo escolhido, os parâmetros e o motivo
ARQUIVO_IMPORTANCIAS = COMPARACAO / "importancias.csv"  # importância de cada coluna do X, por modelo (soma 1)
ARQUIVO_TEMPOS = COMPARACAO / "tempos.csv"  # tempos de treino e previsão, impressos e gravados à parte

# --- Exportação do modelo escolhido (SPEC-comparacao-modelos.md, "Exportação"; tasks/todo-comparacao-modelos.md, M6) ---
# `exportar` lê `escolha.json` (gravado pelo `comparar`), refaz o modelo escolhido e a árvore ajustada só com o treino, e
# grava em `data/modelo/exportado/` (ignorada pelo git). O `.joblib` é um pickle: abrir executa código, por isso o LEIA-ME
# traz o SHA-256 e o aviso. Nada é gravado aqui se alguma checagem falhar.
EXPORTADO = MODELO / "exportado"
ARQUIVO_MODELO_FINAL = EXPORTADO / "modelo_final.joblib"  # o modelo que a regra escolheu
ARQUIVO_ARVORE_EXPORTADA = EXPORTADO / "arvore_ajustada.joblib"  # a árvore ajustada, em arquivo à parte (legível em regras)
ARQUIVO_LEIA_ME = EXPORTADO / "LEIA-ME.md"
ARQUIVO_EXEMPLO_DE_USO = EXPORTADO / "exemplo_de_uso.py"
# Versão do formato do dicionário gravado no `.joblib`: muda só se a estrutura mudar (o leitor confere antes de usar).
FORMATO_EXPORTADO = 1

# --- Teste único da Tarefa 5 (SPEC-teste-final.md; tasks/plan-teste-final.md) ---------------------------------
# O bloco de teste fica fechado até a abertura (`preditor teste --abrir-o-teste`, uma vez). Tudo o que ela grava vai
# para `data/modelo/teste/` (ignorada pelo git), com estes nomes. O ensaio grava só o carimbo `ensaio_ok.json`.
TESTE = MODELO / "teste"
# Carimbo do ensaio: a abertura só roda com ele válido (hash do modelo e do código de medição). Sem data, para que
# duas execuções do ensaio gravem o mesmo arquivo.
ARQUIVO_ENSAIO_OK = TESTE / "ensaio_ok.json"
# Trava: se existe, o teste já foi aberto (estado `em_andamento` ou `concluido`). O código nunca a apaga.
ARQUIVO_TESTE_ABERTO = TESTE / "TESTE_ABERTO.json"
ARQUIVO_RESULTADO_TESTE = TESTE / "resultado.json"  # modelo, SHA-256, N, data e declaração preditor/detector
ARQUIVO_MATRIZ_TESTE = TESTE / "matriz_teste.csv"  # matriz 3×3 em contagem, modelo e persistência
ARQUIVO_METRICAS_TESTE = TESTE / "metricas_teste.csv"  # as métricas de sempre, mais o acerto por transição
ARQUIVO_IC_GANHO_TESTE = TESTE / "ic_ganho_teste.csv"  # IC 95 % por fluxo do ganho de F1 sobre a persistência
ARQUIVO_CASOS_TESTE = TESTE / "casos_teste.txt"  # os dois casos concretos, com fluxo_id e horário
# Estados da trava (`TESTE_ABERTO.json`, SPEC-teste-final.md, "Travas"): gravada em `em_andamento` ANTES de ler o bloco de
# teste, e trocada para `concluido` só no fim. Existir em qualquer dos dois estados recusa uma nova abertura.
ESTADO_EM_ANDAMENTO = "em_andamento"
ESTADO_CONCLUIDO = "concluido"

# --- Visualização: replay no mapa-múndi (SPEC-visualizacao.md; tasks/plan-visualizacao.md) ---------------
# Bloco exibido (spec, "Bloco exibido: validação"): o teste fica fechado até a Tarefa 5. Trocar o bloco é decisão
# do dono e exige rever as checagens de `visualizacao/execucao.py`, que hoje comparam com a validação.
BLOCO_REPLAY = BLOCO_VALIDACAO
WEB = Path(__file__).resolve().parents[2] / "web"  # a página estática (HTML, CSS e JS)
ARQUIVO_REPLAY = WEB / "dados" / "replay.json"  # saída de `visualizacao/`; a pasta `web/dados/` é ignorada pelo git
# Servidor local da página (`uv run python -m preditor servir`; `visualizacao/servidor.py`). O `python -m http.server` perdia
# arquivos sob concorrência (revisão da V7): atende uma conexão por vez (HTTP/1.0), com fila de 5; com 5 navegadores abrindo
# a página ao mesmo tempo, até 6,5 % das cargas falharam, e se a falha atinge um módulo importado a página fica presa em
# "Carregando o replay..." sem mensagem. Com `ThreadingHTTPServer` + fila de 128 + HTTP/1.1, o revisor mediu 0 falhas em
# 200 cargas (e a mesma coisa só com HTTP/1.1); a V7b repetiu essa medição (relatada na entrega).
ENDERECO_SERVIDOR = "127.0.0.1"  # só a própria máquina: a página é local e não precisa de ninguém de fora
PORTA_SERVIDOR = 8000  # a porta que a documentação e o `.claude/launch.json` já usavam; `--porta N` troca
FILA_DO_SERVIDOR = 128  # `request_queue_size`: conexões esperando na fila (o padrão do Python é 5); 128 é o que o revisor mediu
# Texto do aviso fixo da página (spec, "O que é real e o que é simulado").
AVISO_ROTA = "Rota ilustrativa: os cabos existem, mas o caminho de cada fluxo é simulado."
# Casas decimais do RTT no JSON: milésimo de ms. O RTT só serve para a duração do pulso na tela; mais casas
# só engordariam o arquivo (decisão da V1).
CASAS_RTT_REPLAY = 3
# Casas decimais das 8 colunas do X de cada medição no JSON (`x`, só para o cartão do fluxo). 4 = as casas do limiar
# impresso nas regras (`CASAS_LIMIAR_REGRA`): mais do que isso engordaria o arquivo sem mudar o que se lê. A execução
# confere que o valor arredondado cai na MESMA folha que o exato (senão, aumente este número).
CASAS_X_REPLAY = 4
# Casas do limiar de cada divisão no painel da árvore (`arvores.*.nos` no JSON, SPEC-arvore-na-pagina.md). 6 = as da
# ajustada (`CASAS_LIMIAR_REGRA_AJUSTE`), que bastam para as duas: a execução confere que percorrer os nós com o `x` do
# JSON e estes limiares chega na folha gravada.
CASAS_LIMIAR_REPLAY = 6

# Pontos candidatos do destino de cada país (spec, "Coordenadas"), em [longitude, latitude] (ordem do GeoJSON e do D3).
# O dataset só tem o país do destino (`destination_country`), nunca a cidade: cada ponto é uma APROXIMAÇÃO, não uma
# medição. Há um único `dst_addr` por país (conferido no Gold em 01/10/2026). Cada destino recebe depois um pequeno
# deslocamento por `dst_addr` (`DESLOCAMENTO_DESTINO_GRAUS`) para não ficarem empilhados. Quando um país tem mais de um
# ponto candidato, `visualizacao/rotas.py` escolhe entre eles junto com a rota (só entram as combinações fisicamente
# possíveis: RTT mínimo teórico <= mediana real do baseline do fluxo).
PONTOS_DESTINO = {
    # Belo Horizonte: ESTE destino não é inferido, vem do registro do IP. 150.164.1.222 está no bloco 150.164.0.0/16, que
    # o RDAP do Registro.br (https://rdap.registro.br/ip/150.164.1.222, conferido em 01/10/2026) registra em nome da
    # Universidade Federal de Minas Gerais (UFMG), ASN 271354, o mesmo ASN da sonda 6891 (`sondas.csv`), que fica em
    # Belo Horizonte e mede ~0,4 ms até ele. Ponto = centro da cidade (a UFMG fica na região da Pampulha, a poucos km).
    "BR": [("Belo Horizonte", [-43.94, -19.92])],
    "JP": [("Tóquio", [139.69, 35.69])],
    "SG": [("Singapura", [103.82, 1.35])],
    # ATENÇÃO, US: o ponto do destino é INFERIDO do RTT medido, NÃO vem do registro do IP. 92.38.132.60 é de um bloco
    # da G-Core (RDAP do RIPE: GCL-CUSTOMER-US, "G-Core Labs Customer assignment"), provavelmente anycast, de
    # localização desconhecida: o país "US" do dataset é o do registro, e o IP pode responder de qualquer ponto de
    # presença. Pelo RTT, a sonda de Fortaleza (mediana de 65 ms) e a de BH (97 ms) chegam a ele mais depressa do que
    # Nova York permite (RTT mínimo teórico de ~84 e ~103 ms pelos melhores cabos), então a Flórida (Miami) entra como
    # segundo candidato. Nenhum dos dois pontos foi observado: quem escolhe entre eles é o filtro de RTT, e a página
    # mostra o aviso de rota ilustrativa.
    "US": [("Nova York", [-74.01, 40.71]), ("Miami", [-80.19, 25.76])],
    "DE": [("Frankfurt", [8.68, 50.11])],
    "PT": [("Lisboa", [-9.14, 38.72])],
}

# --- Visualização, V3: sondas (SPEC-visualizacao.md, "Decisões do dono", item 1) -------------------------
# Coordenadas das sondas: consultadas UMA vez na API pública do RIPE Atlas (sem chave) por
# `visualizacao/coletar_sondas.py` e versionadas neste CSV. O `replay` só lê o arquivo e continua offline.
ARQUIVO_SONDAS = Path(__file__).resolve().parent / "visualizacao" / "sondas.csv"
URL_API_SONDA = "https://atlas.ripe.net/api/v2/probes/{prb_id}/"  # documentação: https://atlas.ripe.net/docs/apis/rest-api-manual/probes/
TIMEOUT_API_SEGUNDOS = 30  # espera máxima por resposta da API (decisão da V3)

# --- Visualização, V3: rota simulada em trechos (SPEC-visualizacao.md, "Rota simulada") -----------------
# A rota de um fluxo é SIMULADA: o dataset é de ping e não tem traceroute. Os cabos e os pontos de troca de tráfego
# existem; o caminho que cada fluxo faz por eles é escolha nossa. Tudo em [longitude, latitude], com longitude
# sempre em [-180, 180] (as rotas do Pacífico cruzam o meridiano 180: o haversine lida com isso, não "desdobre").

# Distância e RTT mínimo teórico (spec, "Distância e RTT mínimo"). A luz anda na fibra a cerca de 2/3 da velocidade
# dela no vácuo (~300.000 km/s), ou seja, ~200 km por ms. RTT mínimo = ida e volta = 2 × km / 200.
VELOCIDADE_FIBRA_KM_POR_MS = 200
RAIO_TERRA_KM = 6371.0088  # raio médio da Terra (valor da IUGG), usado na distância em círculo máximo (haversine)
CASAS_KM = 1  # casas decimais dos km no JSON (decisão da V3: décimo de km é mais que suficiente)
CASAS_COORDENADA = 4  # casas decimais das coordenadas no JSON: 0,0001° ~ 11 m (decisão da V3)
# Deslocamento máximo, em graus, do destino em relação ao ponto do país, para os destinos do mesmo país não ficarem
# empilhados. 0,2° ~ 22 km: dentro da região metropolitana da cidade (decisão da V3).
DESLOCAMENTO_DESTINO_GRAUS = 0.2

# Estações de aterragem (onde o cabo chega à costa), usadas pelos cabos abaixo. Coordenadas aproximadas da cidade, a
# 0,01°, conferidas contra a posição das estações no mapa da TeleGeography (https://www.submarinecablemap.com): a
# estação real fica a alguns km, o que não muda nada para a página. Nenhum arquivo de geometria da TeleGeography
# (licença não comercial) foi copiado: o mapa só serviu para conferir.
ATERRAGENS = {
    "Fortaleza": [-38.54, -3.72],  # Fortaleza, Brasil
    "Santos": [-46.33, -23.96],  # Santos, Brasil
    "Praia Grande": [-46.41, -24.01],  # Praia Grande, Brasil
    "Sines": [-8.87, 37.96],  # Sines, Portugal
    "Bilbao": [-2.95, 43.30],  # Bilbao (Sopelana), Espanha
    "Boca Raton": [-80.09, 26.35],  # Boca Raton, Flórida, EUA
    "Wall Township": [-74.06, 40.15],  # Wall Township, Nova Jersey, EUA
    "Virginia Beach": [-76.05, 36.80],  # Virginia Beach, Virgínia, EUA
    "Bandon": [-124.41, 43.12],  # Bandon, Oregon, EUA
    "Hermosa Beach": [-118.40, 33.86],  # Hermosa Beach, Califórnia, EUA
    "Maruyama": [139.98, 35.01],  # Maruyama (Minamiboso), Japão
    "Chikura": [139.95, 34.98],  # Chikura (Minamiboso), Japão
    "Tuas": [103.65, 1.34],  # Tuas, Singapura
}

# Catálogo de cabos submarinos. Cada cabo foi conferido em 01/10/2026 na API pública do mapa da TeleGeography
# (https://www.submarinecablemap.com/api/v3/cable/<slug>.json): nome, estações de aterragem usadas e "em serviço"
# (`is_planned` = falso e ano de entrada em operação, "rfs", já passado). Cabo que não foi confirmado ficou de fora.
# `pontos` é o traçado simplificado, escrito à mão, em ordem: o texto é uma estação de `ATERRAGENS` e a lista
# [lon, lat] é um ponto no mar, só o suficiente para a linha não cortar continente (a rota usa o trecho entre duas
# estações, em qualquer sentido). Os cabos reais fazem mais paradas do que as listadas aqui.
CABOS = {
    # Fonte: .../cable/ellalink: 6.200 km, em serviço desde 2021 (jun). Aterragens usadas aqui: Fortaleza e Sines
    # (também tem Belém, São Luís, Praia, Funchal, Gran Canaria e outras, que não entram na rota).
    # Pontos no mar: perto de Cabo Verde e das Canárias, como o cabo real, e a entrada em Sines por sudoeste.
    "EllaLink": {
        "fonte": "https://www.submarinecablemap.com/submarine-cable/ellalink",
        "pontos": ["Fortaleza", [-30.0, 6.0], [-24.5, 15.5], [-19.0, 30.0], [-12.0, 36.5], "Sines"],
    },
    # Fonte: .../cable/monet: 10.556 km, em serviço desde 2017 (dez). Aterragens: Santos, Fortaleza e Boca Raton (as três).
    # Pontos no mar: ao largo da costa brasileira, das Guianas e do Caribe (ao norte de Porto Rico) e a entrada em
    # Boca Raton por cima do norte das Bahamas (a linha não passa por cima das ilhas).
    "Monet": {
        "fonte": "https://www.submarinecablemap.com/submarine-cable/monet",
        "pontos": [
            "Santos", [-44.0, -25.6], [-41.0, -23.9], [-37.5, -17.5], [-36.5, -13.0], [-33.0, -8.0], [-33.5, -5.0],
            "Fortaleza",
            [-37.0, 0.0], [-45.0, 6.0], [-54.0, 10.5], [-60.5, 18.8], [-66.0, 22.5], [-71.0, 25.5], [-76.0, 29.0],
            "Boca Raton",
        ],
    },
    # Fonte: .../cable/seabras-1: 10.800 km, em serviço desde 2017 (set). Aterragens: Praia Grande e Wall Township (as duas).
    # Pontos no mar: sai para leste, sobe pelo Atlântico e entra em Nova Jersey a oeste das Bermudas.
    "Seabras-1": {
        "fonte": "https://www.submarinecablemap.com/submarine-cable/seabras-1",
        "pontos": ["Praia Grande", [-39.0, -26.0], [-28.0, -6.0], [-40.0, 15.0], [-68.0, 33.5], "Wall Township"],
    },
    # Fonte: .../cable/marea: 6.605 km, em serviço desde 2018 (mai). Aterragens: Virginia Beach e Bilbao (as duas).
    # Pontos no mar: um intermediário no Atlântico Norte, sem passar pelas ilhas, e um no Golfo da Biscaia (a linha direta
    # de [-45, 41] até Bilbao cortaria a costa cantábrica; o ponto faz o cabo entrar em Bilbao pelo norte, pelo mar).
    "MAREA": {
        "fonte": "https://www.submarinecablemap.com/submarine-cable/marea",
        "pontos": ["Virginia Beach", [-45.0, 41.0], [-5.0, 44.8], "Bilbao"],
    },
    # Fonte: .../cable/faster: 11.629 km, em serviço desde 2016 (jun). Aterragens usadas: Bandon e Chikura (também
    # Shima e Tanshui). Pontos no mar: o arco norte do Pacífico, cruzando o meridiano 180, e a entrada em Chikura por leste.
    "FASTER": {
        "fonte": "https://www.submarinecablemap.com/submarine-cable/faster",
        "pontos": ["Bandon", [-150.0, 47.0], [-178.0, 46.5], [160.0, 40.0], [146.0, 33.0], "Chikura"],
    },
    # Fonte: .../cable/jupiter: 14.557 km, em serviço desde 2020. Aterragens usadas: Hermosa Beach e Maruyama (também
    # Cloverdale, Shima e Daet). Pontos no mar: o Pacífico em arco mais ao sul que o FASTER, cruzando o meridiano 180.
    "JUPITER": {
        "fonte": "https://www.submarinecablemap.com/submarine-cable/jupiter",
        "pontos": ["Hermosa Beach", [-125.0, 33.0], [-150.0, 37.0], [-175.0, 39.5], [165.0, 38.5], [148.0, 33.0], "Maruyama"],
    },
    # Fonte: .../cable/southeast-asia-japan-cable-sjc: 8.900 km, em serviço desde 2013 (jun). Aterragens usadas: Chikura
    # e Tuas (também Telisai, Chung Hom Kok, Shantou e Nasugbu). Pontos no mar: ao sul do Japão, pelo canal de Bashi,
    # pelo Mar da China Meridional e pelo estreito de Singapura.
    "SJC": {
        "fonte": "https://www.submarinecablemap.com/submarine-cable/southeast-asia-japan-cable-sjc",
        "pontos": [
            "Chikura", [135.0, 31.5], [125.0, 22.0], [121.0, 20.0], [116.0, 16.0], [112.0, 8.0], [107.0, 5.0],
            [104.6, 1.05], [104.0, 1.1],
            "Tuas",
        ],
    },
}

# Pontos de troca de tráfego e cidades-hub por terra (nós `pop`). Cidade ou PTT/IX que existe (conferidos em
# 01/10/2026 na API pública do PeeringDB, https://www.peeringdb.com/api/ix); a coordenada é a do centro da cidade.
HUBS = {
    "IX.br São Paulo": [-46.63, -23.55],
    "IX.br Rio de Janeiro": [-43.17, -22.91],
    "IX.br Belo Horizonte": [-43.94, -19.92],
    "IX.br Fortaleza": [-38.54, -3.73],
    "IX.br Salvador": [-38.50, -12.97],
    "IX.br Porto Alegre": [-51.23, -30.03],
    "IX.br Curitiba": [-49.27, -25.43],
    "ESPANIX Madri": [-3.70, 40.42],
    "Equinix Atlanta": [-84.39, 33.75],
    "Equinix Ashburn": [-77.49, 39.04],
    "Equinix Chicago": [-87.63, 41.88],
    "Equinix Dallas": [-96.80, 32.78],
}
# O primeiro pop de toda rota: o IX.br mais perto da sonda (decisão da V3: a sonda sai pelo ponto de troca da região
# dela; senão uma sonda de Fortaleza passaria por São Paulo para voltar a Fortaleza).
IXS_BRASIL = (
    "IX.br São Paulo", "IX.br Rio de Janeiro", "IX.br Belo Horizonte", "IX.br Fortaleza",
    "IX.br Salvador", "IX.br Porto Alegre", "IX.br Curitiba",
)
# Quando o IX.br mais perto da sonda está no Sul, o backbone para o norte passa antes por outro IX.br: a reta direta
# entre os dois pontos cortaria o mar na costa de Santa Catarina (decisão da V3, conferida contra o contorno do mapa).
PASSAGEM_APOS_IX_LOCAL = {"IX.br Porto Alegre": "IX.br Curitiba"}

# Rotas possíveis por país de destino (spec: 1 a 3 por região; os destinos do dataset são por país). Uma rota é uma
# LISTA DE ETAPAS, em ordem, e cada etapa é um de dois formatos (o "mini-formato"):
#   {"terrestre": nome, "via": [pops], "ate": estação ou "destino"}  → backbone por terra a partir de onde a rota está,
#       passando pelos `via` (cidades-hub de `HUBS`, na ordem) até uma estação de `ATERRAGENS` ou o "destino";
#       `ate` também pode ser uma LISTA de estações: vale a mais perto de onde a rota está (assim uma sonda de
#       Fortaleza entra no Monet em Fortaleza, em vez de ir a Santos e voltar);
#   {"cabo": nome, "ate": estação}                                    → cabo de `CABOS`, da estação onde a rota está
#       até a estação `ate`, em qualquer sentido do cabo.
# Uma opção ainda pode ter `"destinos": [cidades]` (nomes de `PONTOS_DESTINO`): ela só vale para esses pontos do país.
# Sem a chave, vale para todos.
#
# Exemplo completo, a opção "Monet por Fortaleza" para Nova York, lida etapa por etapa (a sonda fica em BH):
#   {"nome": "Monet por Fortaleza", "destinos": ["Nova York"], "etapas": [
#       {"terrestre": "backbone BR", "via": [], "ate": "Fortaleza"},     # sonda → IX.br de BH → estação de Fortaleza
#       {"cabo": "Monet", "ate": "Boca Raton"},                          # Fortaleza → Boca Raton (Flórida), pelo mar
#       {"terrestre": "backbone EUA", "via": ["Equinix Atlanta"], "ate": "destino"},  # Boca Raton → Atlanta → Nova York
#   ]}
#
# A primeira etapa começa na sonda e passa antes pelo IX.br mais perto dela (`IXS_BRASIL`). `visualizacao/rotas.py`
# combina cada opção com cada ponto candidato do país, descarta as combinações com RTT mínimo teórico acima da mediana
# real do fluxo (fisicamente impossíveis) e escolhe uma das que sobram com a semente do projeto + o `fluxo_id`. Região
# = Brasil (BR), América do Norte (US), Europa (DE, PT) e Ásia (JP, SG). Os desvios por terra (Atlanta, Dallas,
# Chicago, Ashburn, Madri) são nossa escolha, só para o backbone não cortar o mar nem dar a volta.
ROTAS_POR_PAIS = {
    # Dentro do Brasil não há cabo: a sonda sai pelo IX.br da região dela e segue por terra até o destino (Porto Alegre
    # passa antes por Curitiba, `PASSAGEM_APOS_IX_LOCAL`). Uma opção só: "via IX.br São Paulo" era a mesma rota para as
    # sondas de SP e um desvio sem motivo para as de BH e do Nordeste.
    "BR": [
        {"nome": "backbone BR", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "destino"},
        ]},
    ],
    # Os EUA têm dois pontos candidatos (ver `PONTOS_DESTINO`). Nova York vem pelo Seabras-1 (Nova Jersey) ou pelo Monet
    # (Flórida, e sobe por Atlanta para o backbone não cortar o mar); Miami fica a poucos km de Boca Raton, só pelo Monet.
    # O Monet tem duas entradas: "Monet" entra pela estação mais perto da sonda (Santos ou Fortaleza) e "Monet por
    # Fortaleza" sempre por Fortaleza (BH e o Nordeste chegam lá por terra, mais perto que dar a volta por Santos).
    # Para sondas já no Nordeste as duas dão a mesma rota, e `rotas.py` guarda só uma delas.
    "US": [
        {"nome": "Seabras-1", "destinos": ["Nova York"], "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Praia Grande"},
            {"cabo": "Seabras-1", "ate": "Wall Township"},
            {"terrestre": "backbone EUA", "via": [], "ate": "destino"},
        ]},
        {"nome": "Monet", "destinos": ["Nova York"], "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": ["Santos", "Fortaleza"]},
            {"cabo": "Monet", "ate": "Boca Raton"},
            {"terrestre": "backbone EUA", "via": ["Equinix Atlanta"], "ate": "destino"},
        ]},
        {"nome": "Monet por Fortaleza", "destinos": ["Nova York"], "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Fortaleza"},
            {"cabo": "Monet", "ate": "Boca Raton"},
            {"terrestre": "backbone EUA", "via": ["Equinix Atlanta"], "ate": "destino"},
        ]},
        {"nome": "Monet", "destinos": ["Miami"], "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": ["Santos", "Fortaleza"]},
            {"cabo": "Monet", "ate": "Boca Raton"},
            {"terrestre": "backbone EUA", "via": [], "ate": "destino"},
        ]},
        {"nome": "Monet por Fortaleza", "destinos": ["Miami"], "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Fortaleza"},
            {"cabo": "Monet", "ate": "Boca Raton"},
            {"terrestre": "backbone EUA", "via": [], "ate": "destino"},
        ]},
    ],
    "PT": [
        {"nome": "EllaLink", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Fortaleza"},
            {"cabo": "EllaLink", "ate": "Sines"},
            {"terrestre": "backbone Portugal", "via": [], "ate": "destino"},
        ]},
        {"nome": "Seabras-1 + MAREA", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Praia Grande"},
            {"cabo": "Seabras-1", "ate": "Wall Township"},
            {"terrestre": "backbone EUA", "via": ["Equinix Ashburn"], "ate": "Virginia Beach"},
            {"cabo": "MAREA", "ate": "Bilbao"},
            {"terrestre": "backbone Europa", "via": [], "ate": "destino"},
        ]},
    ],
    "DE": [
        {"nome": "EllaLink", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Fortaleza"},
            {"cabo": "EllaLink", "ate": "Sines"},
            {"terrestre": "backbone Europa", "via": ["ESPANIX Madri"], "ate": "destino"},
        ]},
        {"nome": "Seabras-1 + MAREA", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Praia Grande"},
            {"cabo": "Seabras-1", "ate": "Wall Township"},
            {"terrestre": "backbone EUA", "via": ["Equinix Ashburn"], "ate": "Virginia Beach"},
            {"cabo": "MAREA", "ate": "Bilbao"},
            {"terrestre": "backbone Europa", "via": ["ESPANIX Madri"], "ate": "destino"},
        ]},
    ],
    "JP": [
        {"nome": "Monet + JUPITER", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": ["Santos", "Fortaleza"]},
            {"cabo": "Monet", "ate": "Boca Raton"},
            {"terrestre": "backbone EUA", "via": ["Equinix Atlanta", "Equinix Dallas"], "ate": "Hermosa Beach"},
            {"cabo": "JUPITER", "ate": "Maruyama"},
            {"terrestre": "backbone Japão", "via": [], "ate": "destino"},
        ]},
        {"nome": "Seabras-1 + FASTER", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Praia Grande"},
            {"cabo": "Seabras-1", "ate": "Wall Township"},
            {"terrestre": "backbone EUA", "via": ["Equinix Chicago"], "ate": "Bandon"},
            {"cabo": "FASTER", "ate": "Chikura"},
            {"terrestre": "backbone Japão", "via": [], "ate": "destino"},
        ]},
    ],
    "SG": [
        {"nome": "Monet + JUPITER + SJC", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": ["Santos", "Fortaleza"]},
            {"cabo": "Monet", "ate": "Boca Raton"},
            {"terrestre": "backbone EUA", "via": ["Equinix Atlanta", "Equinix Dallas"], "ate": "Hermosa Beach"},
            {"cabo": "JUPITER", "ate": "Maruyama"},
            {"terrestre": "backbone Japão", "via": [], "ate": "Chikura"},
            {"cabo": "SJC", "ate": "Tuas"},
            {"terrestre": "backbone Singapura", "via": [], "ate": "destino"},
        ]},
        {"nome": "Seabras-1 + FASTER + SJC", "etapas": [
            {"terrestre": "backbone BR", "via": [], "ate": "Praia Grande"},
            {"cabo": "Seabras-1", "ate": "Wall Township"},
            {"terrestre": "backbone EUA", "via": ["Equinix Chicago"], "ate": "Bandon"},
            {"cabo": "FASTER", "ate": "Chikura"},
            {"cabo": "SJC", "ate": "Tuas"},
            {"terrestre": "backbone Singapura", "via": [], "ate": "destino"},
        ]},
    ],
}
