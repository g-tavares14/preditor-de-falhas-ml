"""Servidor local da página do replay: `uv run python -m preditor servir` (SPEC-visualizacao.md, "Comandos").

Só biblioteca padrão, sem Spark e sem Java. Existe porque o `python -m http.server` perdia arquivos quando vários
navegadores abriam a página juntos (ver o comentário das constantes em `config.py`).
"""

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from preditor import config


class Atendente(SimpleHTTPRequestHandler):
    """Entrega os arquivos de `web/`, com os tipos e os cabeçalhos que a página espera."""

    # HTTP/1.1 deixa o navegador reaproveitar a conexão para os ~25 arquivos da página; no padrão (HTTP/1.0) cada
    # arquivo abre e fecha uma conexão. Para isso toda resposta tem de trazer `Content-Length`: a `SimpleHTTPRequestHandler`
    # já traz, nos arquivos, nos redirecionamentos e nos erros.
    protocol_version = "HTTP/1.1"

    # Tipos escritos aqui (e não deixados ao `mimetypes` do sistema, que varia): um módulo JavaScript servido com tipo
    # errado é recusado pelo navegador.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".json": "application/json",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".html": "text/html",
    }

    def end_headers(self) -> None:
        # `no-cache` = o navegador pergunta se o arquivo mudou antes de usar a cópia dele: o `replay.json` é regravado
        # a cada `replay`, e o código da página muda enquanto se desenvolve.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_request(self, code="-", size="-") -> None:
        # Só os pedidos que deram erro (404 etc.): uma carga da página são ~25 linhas que não dizem nada de útil.
        if str(code).isdigit() and int(code) >= 400:
            super().log_request(code, size)


class ServidorDaPagina(ThreadingHTTPServer):
    """Uma thread por conexão (a página abre vários arquivos ao mesmo tempo e um não espera o outro), com fila maior."""

    request_queue_size = config.FILA_DO_SERVIDOR
    # As threads das conexões não seguram o encerramento: Ctrl+C sai na hora, mesmo com o navegador conectado.
    daemon_threads = True


class Servidor:
    def servir(self, porta: int) -> None:
        # Sem o JSON do replay a página só mostraria a mensagem de erro: pede o comando antes de subir.
        if not config.ARQUIVO_REPLAY.exists():
            raise SystemExit(f"Não encontrei {config.ARQUIVO_REPLAY}.\nRode antes: uv run python -m preditor replay")

        if not 1 <= porta <= 65535:
            raise SystemExit(f"Porta inválida: {porta}. Use um número de 1 a 65535.")

        # A pasta é fixa (`config.WEB`), não a do diretório de onde o comando foi chamado.
        atendente = functools.partial(Atendente, directory=str(config.WEB))
        try:
            servidor = ServidorDaPagina((config.ENDERECO_SERVIDOR, porta), atendente)
        except OSError as erro:
            raise SystemExit(f"Não consegui usar a porta {porta} ({erro.strerror}).\nUse outra: uv run python -m preditor servir --porta N")

        print(f"Página em http://{config.ENDERECO_SERVIDOR}:{porta}/ (Ctrl+C encerra)")
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")
        finally:
            servidor.server_close()
