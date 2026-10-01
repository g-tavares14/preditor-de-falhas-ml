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
