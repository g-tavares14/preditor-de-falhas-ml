"""Ponto de entrada do serviço ao vivo sem passar pelo `preditor/__main__.py`, que importa o PySpark: `python -m preditor.aovivo`.

Existe para o contêiner (SPEC-api-csharp.md, módulo `implantacao-aws`), que não leva Spark nem Java. Aceita as mesmas opções do
`uv run python -m preditor aovivo` e chama a mesma `ExecucaoAoVivo`. No contêiner o Gold não existe: use `--sem-conferir`.
"""

import argparse

from preditor.aovivo import parametros
from preditor.aovivo.execucao import ExecucaoAoVivo


def main() -> None:
    leitor = argparse.ArgumentParser(prog="python -m preditor.aovivo", description="Serviço ao vivo (SPEC-ao-vivo.md), sem Spark.")
    leitor.add_argument("--conferir", action="store_true", help="confere o motor contra o Gold e o leitor contra o Silver (usa a API) e sai")
    leitor.add_argument("--sem-conferir", action="store_true", help="pula a conferência do motor contra o Gold na partida (sem o Gold, como no contêiner)")
    leitor.add_argument("--recomecar", action="store_true", help="apaga o estado, sorteia as sondas e calcula o baseline de novo")
    leitor.add_argument("--quantas", type=int, default=parametros.SONDAS_PADRAO, help=f"quantas sondas sortear (padrão {parametros.SONDAS_PADRAO})")
    leitor.add_argument("--paises", default=None, help="países das sondas, em código de 2 letras separados por vírgula (padrão: América Latina)")
    leitor.add_argument("--retroativo-horas", type=float, default=0.0, help="T0 fica tantas horas no passado")
    leitor.add_argument("--ciclos", type=int, default=None, help="para depois de tantas consultas (padrão: roda até ser parado)")
    ExecucaoAoVivo().executar(leitor.parse_args())


if __name__ == "__main__":
    main()
