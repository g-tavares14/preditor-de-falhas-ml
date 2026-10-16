"""Cálculo do Y: rótulo OK / RISCO / FALHA de cada medição do Período B.

`rotulo.py` aplica a regra da RFC §8.4 e acrescenta `regra`, `status_atual` e `status_futuro` às features.
`recorte.py` acrescenta `bloco` (treino / validacao / teste), por dois instantes de corte iguais para todos os fluxos.
"""
