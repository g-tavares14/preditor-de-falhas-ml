"""Coleta, uma única vez, as coordenadas das sondas na API pública do RIPE Atlas (SPEC-visualizacao.md).

Roda à parte, com rede: `uv run python -m preditor.visualizacao.coletar_sondas`.
Lê do Gold quais sondas existem, consulta `https://atlas.ripe.net/api/v2/probes/<id>/` (pública, sem chave) e grava
`visualizacao/sondas.csv`, que fica no git. O comando `replay` só lê esse CSV e continua offline.

Usa `urllib` da biblioteca padrão: `requests` não é dependência do pacote (só do grupo `notebook`).
"""

import http.client
import json
import urllib.request

import pandas as pd

from preditor import config
from preditor.visualizacao.rotas import Sondas

COLUNAS_CSV = ["prb_id", "longitude", "latitude", "pais", "asn"]


class ColetaSondas:
    @staticmethod
    def consultar(prb_id: int) -> dict:
        """Uma sonda na API. Devolve o JSON dela; erro de rede ou resposta inválida sobe como exceção (tratada em `executar`)."""
        url = config.URL_API_SONDA.format(prb_id=prb_id)
        with urllib.request.urlopen(url, timeout=config.TIMEOUT_API_SEGUNDOS) as resposta:
            return json.loads(resposta.read().decode("utf-8"))

    @staticmethod
    def extrair_linha(prb_id: int, resposta: dict) -> dict:
        """As colunas do CSV a partir da resposta da API; levanta `ValueError` se não houver coordenada."""
        geometria = resposta.get("geometry")
        # `geometry.coordinates` = [longitude, latitude] (GeoJSON). A API devolve `null` quando a sonda não tem posição.
        if not geometria or not geometria.get("coordinates"):
            raise ValueError("a API não devolveu coordenadas")
        longitude, latitude = geometria["coordinates"]
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise ValueError(f"coordenada inválida: {longitude}, {latitude}")
        return {
            "prb_id": prb_id,
            "longitude": longitude,
            "latitude": latitude,
            # Colunas só informativas (a API não dá cidade). Podem vir vazias: a sonda pode não ter IPv4.
            "pais": resposta.get("country_code"),
            "asn": resposta.get("asn_v4"),
        }

    def executar(self) -> None:
        sondas = Sondas.do_gold()
        print(f"{len(sondas)} sondas no Gold: {sondas}")

        linhas = []
        falhas = {}  # prb_id → motivo
        for prb_id in sondas:
            try:
                linhas.append(self.extrair_linha(prb_id, self.consultar(prb_id)))
            # `OSError` cobre `URLError` (sem rede, HTTP 4xx/5xx), `TimeoutError` e conexão interrompida;
            # `HTTPException`, a resposta HTTP malformada ou cortada; `ValueError`, o JSON inválido
            # (`JSONDecodeError`) e a coordenada ausente ou fora da faixa. Tudo vira "sonda sem coordenada" abaixo.
            except (OSError, http.client.HTTPException, ValueError) as erro:
                falhas[prb_id] = str(erro)

        # Qualquer falha para tudo: o CSV só é gravado completo (decisão do dono: sonda sem coordenada, perguntar).
        if falhas:
            for prb_id, motivo in falhas.items():
                print(f"  sonda {prb_id}: {motivo}")
            raise SystemExit(f"{len(falhas)} sonda(s) sem coordenada: {sorted(falhas)}. O CSV não foi gravado.")

        tabela = pd.DataFrame(linhas, columns=COLUNAS_CSV).sort_values("prb_id")
        # `Int64` aceita o ASN vazio sem virar decimal ("36236.0").
        tabela["asn"] = tabela["asn"].astype("Int64")
        config.ARQUIVO_SONDAS.parent.mkdir(parents=True, exist_ok=True)
        tabela.to_csv(config.ARQUIVO_SONDAS, index=False)
        print(f"Gravado: {config.ARQUIVO_SONDAS}")
        print(tabela.to_string(index=False))


if __name__ == "__main__":
    ColetaSondas().executar()
