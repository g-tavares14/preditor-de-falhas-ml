"""Parâmetros do microserviço do modelo (SPEC-api-csharp.md). Ficam aqui e não em `config.py`, que foi congelado quando o
teste final foi aberto (10/10/2026, AGENTS.md): o que já existe lá (colunas, classes, semente) é LIDO de `config`, nunca copiado."""

from pathlib import Path

from preditor_analise import config

PORTA_PADRAO = 8001
ENDERECO_PADRAO = "127.0.0.1"  # no contêiner o Compose passa `--endereco 0.0.0.0`; a porta nunca é publicada

MAXIMO_MEDICOES = 1000  # linhas por pedido: o servidor em Go manda uma por vez, o teste de paridade manda lotes
MAXIMO_CORPO_BYTES = 1_000_000  # 1 MB; acima disso o serviço recusa sem ler (413)
FILA_DO_SERVIDOR = 128  # `request_queue_size`: conexões esperando na fila (o padrão do Python é 5, que perdia conexões sob concorrência)

# --- A amostra de paridade (`--conferir`) ---------------------------------------------------------------------
ARQUIVO_PARIDADE = Path(__file__).resolve().parents[3] / "servidor" / "internal" / "api" / "testdata" / "paridade.json"
LINHAS_COM_NAN = 100  # linhas com algum valor ausente: é onde o ONNX divergia, e o Go tem de acertar também
LINHAS_POR_CLASSE = 70  # linhas sem NaN por classe prevista, para as três classes aparecerem (total ~310)
