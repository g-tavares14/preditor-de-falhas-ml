"""Parâmetros do microserviço do modelo (SPEC-api-csharp.md). Ficam aqui e não em `config.py`, que faz parte do código de
medição do carimbo do teste (AGENTS.md): o que já existe lá (colunas, classes, semente) é LIDO de `config`, nunca copiado."""

from pathlib import Path

from preditor_analise import config

PORTA_PADRAO = 8001
ENDERECO_PADRAO = "127.0.0.1"  # no contêiner o Compose passa `--endereco 0.0.0.0`; a porta nunca é publicada

MAXIMO_MEDICOES = 1000  # linhas por pedido: a API em C# manda uma por vez, o teste de paridade manda lotes
MAXIMO_CORPO_BYTES = 1_000_000  # 1 MB; acima disso o serviço recusa sem ler (413)
FILA_DO_SERVIDOR = config.FILA_DO_SERVIDOR  # a mesma fila do servidor da página

# --- A amostra de paridade (`--conferir`) ---------------------------------------------------------------------
ARQUIVO_PARIDADE = Path(__file__).resolve().parents[3] / "api" / "Preditor.Api.Tests" / "Fixtures" / "paridade.json"
LINHAS_COM_NAN = 100  # linhas com algum valor ausente: é onde o ONNX divergia, e o C# tem de acertar também
LINHAS_POR_CLASSE = 70  # linhas sem NaN por classe prevista, para as três classes aparecerem (total ~310)
