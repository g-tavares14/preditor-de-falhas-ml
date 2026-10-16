"""Cliente da API pública do RIPE Atlas e o leitor de um resultado de ping (SPEC-ao-vivo.md).

Usa `urllib` da biblioteca padrão, como `visualizacao/coletar_sondas.py`: `requests` não é dependência do pacote.
Só lê (GET); a API pública não pede chave para medições públicas.

O leitor (`ler_resultado`) refaz, em Python, o que o Silver faz no Spark (`silver/medicao.py`): o RTT da medição é a média
dos pings válidos da rajada, o jitter é a média de |Δrtt| entre pings consecutivos e a perda vem de enviados e recebidos.
"""

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from preditor import config
from preditor.aovivo import parametros

CAMPOS_DA_SONDA = "id,country_code,geometry,asn_v4,is_anchor,status"


class ErroDaApi(Exception):
    """A API não respondeu depois de todas as tentativas, ou respondeu algo que não é JSON."""


class ClienteAtlas:
    # --- Pedidos -----------------------------------------------------------------------------------------------

    @staticmethod
    def _get(url: str):
        """GET que devolve o JSON. Em erro de rede, 429 ou 5xx tenta de novo (2, 4, 8 s); 4xx que não é 429 sobe na hora."""
        ultimo_erro: Exception | None = None
        for tentativa in range(parametros.TENTATIVAS_API):
            try:
                pedido = urllib.request.Request(url, headers={"User-Agent": "preditor-de-falhas-ml (projeto academico)"})
                with urllib.request.urlopen(pedido, timeout=config.TIMEOUT_API_SEGUNDOS * 2) as resposta:
                    return json.loads(resposta.read().decode("utf-8"))
            except urllib.error.HTTPError as erro:
                if erro.code != 429 and erro.code < 500:
                    raise ErroDaApi(f"HTTP {erro.code} em {url}") from erro
                ultimo_erro = erro
            # `OSError` cobre a falta de rede e o tempo esgotado; `HTTPException`, a resposta cortada; `ValueError`, o JSON inválido.
            except (OSError, http.client.HTTPException, ValueError) as erro:
                ultimo_erro = erro
            time.sleep(2 ** (tentativa + 1))
        raise ErroDaApi(f"sem resposta de {url} depois de {parametros.TENTATIVAS_API} tentativas: {ultimo_erro}")

    # --- Quem participa --------------------------------------------------------------------------------------------

    def participantes(self, msm_id: int) -> set[int]:
        """As sondas que têm resultado recente na medição: `/latest/` devolve o último resultado de cada sonda."""
        resultados = self._get(f"{parametros.URL_API}/measurements/{msm_id}/latest/?format=json")
        return {int(resultado["prb_id"]) for resultado in resultados}

    def sondas_do_pais(self, pais: str) -> list[dict]:
        """As sondas conectadas do país, com coordenada e ASN. Pode ser uma lista vazia."""
        consulta = urllib.parse.urlencode({"country_code": pais, "status": 1, "page_size": 500, "fields": CAMPOS_DA_SONDA})
        pagina = self._get(f"{parametros.URL_API}/probes/?{consulta}")
        return list(pagina["results"])

    # --- Resultados ------------------------------------------------------------------------------------------------

    def resultados(self, msm_id: int, sondas: list[int], inicio: int, fim: int) -> list[dict]:
        """Os resultados da medição para as sondas, com `inicio` <= timestamp <= `fim` (segundos desde 1970, UTC)."""
        consulta = urllib.parse.urlencode(
            {"probe_ids": ",".join(str(sonda) for sonda in sondas), "start": inicio, "stop": fim, "format": "json"}
        )
        resposta = self._get(f"{parametros.URL_API}/measurements/{msm_id}/results/?{consulta}")
        if not isinstance(resposta, list):
            raise ErroDaApi(f"a API devolveu {type(resposta).__name__} em vez de uma lista (medição {msm_id})")
        return resposta


def ler_resultado(resultado: dict) -> dict | None:
    """Um resultado de ping da API → uma linha como a do Silver; `None` se não for um ping com pacotes enviados.

    Colunas: `fluxo_id`, `prb_id`, `dst_addr`, `msm_id`, `t` (segundos UTC), `rtt`, `jitter`, `perda_pct`, `timeout_atual`.
    """
    enviados = resultado.get("sent")
    recebidos = resultado.get("rcvd")
    # Sem pacotes enviados não há perda a calcular (divisão por zero): não é uma medição de ping.
    if resultado.get("type") != "ping" or not enviados or recebidos is None:
        return None

    # RTT válido = rtt > 0 (RTT 0 é o timeout do Atlas; `{"x": "*"}` é um ping sem resposta e `{"error": ...}` um erro).
    # O campo `avg` da API NÃO serve: vale -1 quando nada volta. Reconstrói-se da lista, como o Silver.
    rtts = [ping["rtt"] for ping in resultado.get("result", []) if isinstance(ping.get("rtt"), (int, float)) and ping["rtt"] > 0]

    rtt = sum(rtts) / len(rtts) if rtts else None
    # Jitter = média de |Δrtt| entre pings consecutivos válidos (RFC 3550); precisa de ao menos 2 respostas.
    jitter = sum(abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))) / (len(rtts) - 1) if len(rtts) >= 2 else None
    perda = (enviados - recebidos) / enviados * 100
    prb_id = int(resultado["prb_id"])
    return {
        "fluxo_id": f"{prb_id}|{resultado['dst_addr']}|{int(resultado['msm_id'])}",
        "prb_id": prb_id,
        "dst_addr": resultado["dst_addr"],
        "msm_id": int(resultado["msm_id"]),
        "t": int(resultado["timestamp"]),
        "rtt": rtt,
        "jitter": jitter,
        "perda_pct": perda,
        # Medição inteira sem resposta (rtt nulo) ou perda total (Silver: `rtt` nulo OU `perda_pct` == 100).
        "timeout_atual": int(rtt is None or perda == 100),
    }
