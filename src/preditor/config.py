"""Parâmetros do projeto. Tudo que é "número mágico" fica aqui, com a origem."""

from pathlib import Path

# --- Fonte dos dados (BigQuery) ---------------------------------------------
PROJECT = "atlas-ripe-509700"
TABLE = f"{PROJECT}.atlasRipe.atlas"
LOCATION = "EU"
ORIGEM = "BR"  # todas as probes do recorte são brasileiras (docs/data/README.md)

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
JITTER_RISCO = 3.0  # jitter atual / jitter típico
JANELA = 5  # quantas medições recentes olhamos (a atual + 4 anteriores)
# Linhas 1, 2, 4 e 5 da tabela de rótulo (a linha 3 usa Z_FALHA, acima).
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
DADOS = Path(__file__).resolve().parents[2] / "docs" / "data"
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

# Saídas da árvore oficial em `docs/data/modelo/`. As métricas dela entram nos CSVs de matriz e métricas
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
