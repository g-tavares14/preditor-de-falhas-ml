"""Ponto de entrada do serviço ao vivo sem passar pelo `preditor/__main__.py`, que importa o PySpark: `python -m preditor_servico.aovivo`.

Existe para o contêiner (SPEC-api-csharp.md, módulo `implantacao-aws`), que não leva Spark nem Java. Aceita as mesmas opções do
`uv run python -m preditor_analise aovivo` e chama a mesma `ExecucaoAoVivo`. Este ponto de entrada não confere o motor contra o Gold
(o `preditor_servico` não lê o Gold: no contêiner ele não existe); a conferência está na análise.
"""

import argparse

from preditor_servico.aovivo import parametros
from preditor_servico.aovivo.execucao import ExecucaoAoVivo


def main() -> None:
    leitor = argparse.ArgumentParser(prog="python -m preditor_servico.aovivo", description="Serviço ao vivo (SPEC-ao-vivo.md), sem Spark.")
    leitor.add_argument("--recomecar", action="store_true", help="apaga o estado, sorteia as sondas e calcula o baseline de novo")
    leitor.add_argument("--quantas", type=int, default=parametros.SONDAS_PADRAO, help=f"quantas sondas sortear (padrão {parametros.SONDAS_PADRAO})")
    leitor.add_argument("--paises", default=None, help="países das sondas, em código de 2 letras separados por vírgula (padrão: América Latina)")
    leitor.add_argument("--retroativo-horas", type=float, default=0.0, help="T0 fica tantas horas no passado")
    leitor.add_argument("--ciclos", type=int, default=None, help="para depois de tantas consultas (padrão: roda até ser parado)")
    ExecucaoAoVivo().executar(leitor.parse_args())


if __name__ == "__main__":
    main()
