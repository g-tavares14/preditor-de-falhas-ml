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

# --- Saída ---------------------------------------------------------------------
SAIDA = Path(__file__).resolve().parents[2] / "docs" / "data" / "processed"
