"""Escolhe as sondas do serviço ao vivo: sondas novas, que participam das 6 medições (SPEC-ao-vivo.md)."""

import random

import pandas as pd

from preditor_analise import config
from preditor_servico.aovivo import parametros
from preditor_servico.aovivo.atlas import ClienteAtlas, ler_resultado
from preditor_servico.geografia import Sondas


class Selecao:
    def __init__(self, cliente: ClienteAtlas) -> None:
        self.cliente = cliente

    @staticmethod
    def sondas_do_treino() -> set[int]:
        """Todas as sondas que o projeto já usou: as do `sondas.csv`."""
        # O serviço não lê o Gold (no contêiner ele não existe). O `replay` confere que o `sondas.csv` tem exatamente as
        # sondas do baseline do Gold (`preditor_analise/visualizacao/execucao.py`), então o CSV sozinho dá a mesma lista.
        return set(Sondas.ler())

    def candidatas(self, paises: tuple[str, ...]) -> dict[int, dict]:
        """`prb_id` → país, coordenada e ASN, das sondas dos países que NÃO são do treino e participam das 6 medições."""
        # Participar das 6 é o que dá os 6 fluxos por sonda, com os mesmos destinos do treino.
        participantes = [self.cliente.participantes(msm_id) for msm_id in parametros.DESTINOS]
        em_todas = set.intersection(*participantes)
        treino = self.sondas_do_treino()

        candidatas = {}
        for pais in paises:
            for sonda in self.cliente.sondas_do_pais(pais):
                geometria = sonda.get("geometry")
                # Sem coordenada não há onde pôr a sonda no mapa; sem participar das 6, não há os 6 fluxos.
                if sonda["id"] in treino or sonda["id"] not in em_todas or not geometria or not geometria.get("coordinates"):
                    continue
                longitude, latitude = geometria["coordinates"]
                candidatas[int(sonda["id"])] = {
                    "pais": sonda["country_code"],
                    "longitude": float(longitude),
                    "latitude": float(latitude),
                    "asn": sonda.get("asn_v4"),
                }
        return candidatas

    @staticmethod
    def sortear(candidatas: dict[int, dict], quantas: int) -> dict[int, dict]:
        """Sorteio com a semente do projeto sobre a lista em ordem crescente: o mesmo conjunto dá sempre as mesmas sondas."""
        ordenadas = sorted(candidatas)
        escolhidas = random.Random(config.SEMENTE).sample(ordenadas, min(quantas, len(ordenadas)))
        return {prb_id: candidatas[prb_id] for prb_id in sorted(escolhidas)}

    def baixar_historico(self, sondas: list[int], t0: int) -> pd.DataFrame:
        """As medições das últimas `HORAS_PERIODO_A` horas antes de `t0` (o Período A do serviço), de todas as 6 medições."""
        inicio = t0 - config.HORAS_PERIODO_A * 3600
        passo = parametros.HORAS_POR_PEDIDO * 3600
        linhas = []
        for msm_id in parametros.DESTINOS:
            de = inicio
            while de < t0:
                ate = min(de + passo, t0)
                lidas = (ler_resultado(resultado) for resultado in self.cliente.resultados(msm_id, sondas, de, ate))
                linhas.extend(linha for linha in lidas if linha is not None)
                de = ate + 1  # `start` e `stop` da API são inclusivos: o próximo pedido começa 1 s depois
            print(f"  medição {msm_id}: {len(linhas)} linhas até aqui")
        historico = pd.DataFrame(linhas).drop_duplicates(["fluxo_id", "t"])
        # `t0` é o limite: o que chegar depois é ao vivo (Período B), nunca entra na ficha.
        return historico[(historico["t"] > inicio) & (historico["t"] <= t0)].reset_index(drop=True)
