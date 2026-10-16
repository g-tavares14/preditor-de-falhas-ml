"""O servidor HTTP do microserviço: `POST /prever` e `GET /saude` (SPEC-api-csharp.md). Só biblioteca padrão."""

import json
import platform
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sklearn

from preditor.servico_modelo import parametros
from preditor.servico_modelo.previsor import PedidoInvalido, Previsor


def _recusar_constante(texto: str):
    """`json.loads` aceita `NaN` e `Infinity` por padrão; JSON de verdade não tem. Valor ausente é `null`."""
    raise PedidoInvalido(f"Constante não permitida no JSON: {texto}. Use null para valor ausente.")


class Atendente(BaseHTTPRequestHandler):
    # HTTP/1.1 deixa a API em C# reaproveitar a conexão; para isso toda resposta traz `Content-Length`.
    protocol_version = "HTTP/1.1"
    previsor: Previsor  # preenchido por `criar_servidor`

    def _responder(self, codigo: int, corpo: dict) -> None:
        dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self) -> None:
        if self.path != "/saude":
            return self._responder(404, {"erro": "Rota não encontrada."})
        self._responder(
            200,
            {
                "status": "ok",
                **self.previsor.ficha(),
                "ambiente": {"python": platform.python_version(), "scikit_learn": sklearn.__version__},
            },
        )

    def do_POST(self) -> None:
        if self.path != "/prever":
            return self._responder(404, {"erro": "Rota não encontrada."})
        try:
            tamanho = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._responder(411, {"erro": "Falta o cabeçalho Content-Length."})
        if tamanho > parametros.MAXIMO_CORPO_BYTES:
            # Não lê o corpo: com HTTP/1.1 ele ficaria na conexão, então fecha-a depois da resposta.
            self.close_connection = True
            return self._responder(413, {"erro": f"Corpo maior que {parametros.MAXIMO_CORPO_BYTES} bytes."})
        try:
            pedido = json.loads(self.rfile.read(tamanho), parse_constant=_recusar_constante)
            if not isinstance(pedido, dict):
                raise PedidoInvalido("O corpo tem de ser um objeto com a chave 'medicoes'.")
            previsoes = self.previsor.prever(pedido.get("medicoes"))
        except (PedidoInvalido, ValueError) as erro:  # `json.JSONDecodeError` é um `ValueError`
            return self._responder(400, {"erro": str(erro)})
        self._responder(200, {"previsoes": previsoes, **self.previsor.ficha()})

    def do_PUT(self) -> None:
        self._responder(405, {"erro": "Método não permitido."})

    do_DELETE = do_PATCH = do_PUT

    def log_request(self, code="-", size="-") -> None:
        # Só os pedidos com erro, e sem o corpo: ele traria os valores do cliente para o log.
        if str(code).isdigit() and int(code) >= 400:
            super().log_request(code, size)


class ServidorDoModelo(ThreadingHTTPServer):
    request_queue_size = parametros.FILA_DO_SERVIDOR
    daemon_threads = True


def criar_servidor(previsor: Previsor, endereco: str, porta: int) -> ServidorDoModelo:
    """Um servidor ligado ao previsor. `porta=0` pede ao sistema uma porta livre (usado na conferência)."""
    atendente = type("AtendenteDoModelo", (Atendente,), {"previsor": previsor})
    return ServidorDoModelo((endereco, porta), atendente)
