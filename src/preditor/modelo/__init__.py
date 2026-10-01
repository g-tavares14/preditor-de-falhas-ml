"""Modelo: a árvore de decisão treinada com o Gold (SPEC-arvore.md).

Fora do medalhão: lê `docs/data/gold/` do disco, sem Spark, e grava em `docs/data/modelo/`.
Comando: `uv run python -m preditor arvore`.

- `dados.py`: lê o dataset rotulado, aplica a folga e monta X e y por bloco (o teste fica fechado).
- `avaliacao.py`: matriz 3x3, métricas, persistência e os erros concretos.
- `arvore.py`: busca na grade, treino, regras em texto e a árvore de contraste.
- `regras.py`: as 3 regras em português, lidas do caminho real da árvore.
- `execucao.py`: orquestra, imprime, grava e verifica.
"""
