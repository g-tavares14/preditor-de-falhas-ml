"""Ponto de entrada: `uv run python -m preditor.servico_modelo [--porta N] [--endereco A] [--conferir]`.

Não passa por `preditor/__main__.py`, que importa o PySpark: este serviço sobe sem Spark e sem Java.
"""

import argparse

from preditor.servico_modelo import parametros
from preditor.servico_modelo.conferencia import Conferencia
from preditor.servico_modelo.previsor import Previsor
from preditor.servico_modelo.servidor import criar_servidor
from preditor.visualizacao.modelo_exportado import ModeloExportado


def main() -> None:
    leitor = argparse.ArgumentParser(prog="python -m preditor.servico_modelo", description="Microserviço do modelo (SPEC-api-csharp.md).")
    leitor.add_argument("--porta", type=int, default=parametros.PORTA_PADRAO)
    leitor.add_argument("--endereco", default=parametros.ENDERECO_PADRAO, help="0.0.0.0 só dentro do contêiner")
    leitor.add_argument("--conferir", action="store_true", help="confere o serviço contra o modelo e grava o paridade.json; não fica no ar")
    argumentos = leitor.parse_args()

    if not 1 <= argumentos.porta <= 65535:
        raise SystemExit(f"Porta inválida: {argumentos.porta}. Use um número de 1 a 65535.")

    # O SHA-256 é conferido antes de abrir o pickle; sem os arquivos, a mensagem diz qual comando rodar.
    previsor = Previsor(ModeloExportado.ler())
    if argumentos.conferir:
        Conferencia(previsor).rodar()
        return

    try:
        servidor = criar_servidor(previsor, argumentos.endereco, argumentos.porta)
    except OSError as erro:
        raise SystemExit(f"Não consegui usar a porta {argumentos.porta} ({erro.strerror}).")
    print(f"Modelo {previsor.exportado.sha256[:12]}… em http://{argumentos.endereco}:{argumentos.porta}/ (Ctrl+C encerra)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServiço encerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
