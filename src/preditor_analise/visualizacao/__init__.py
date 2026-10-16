"""Visualização: o replay da validação no mapa-múndi (SPEC-visualizacao.md).

Fora do medalhão e fora de `modelo/`: lê `data/gold/` do disco, sem Spark e sem Java, e grava
`wwwroot/dados/replay.json`, que a página em `wwwroot/` reproduz em tempo acelerado.
Comando: `uv run python -m preditor_analise replay`.

- `exportacao.py`: monta as linhas do replay (medição + previsão + futuro) e as rotas de cada fluxo.
- `execucao.py`: orquestra, grava o JSON e verifica.
"""
