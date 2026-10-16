"""O JSON da página no modo ao vivo (`web/dados/aovivo.json`), no mesmo formato do `replay.json` (SPEC-ao-vivo.md).

A página reaproveita o mapa, o feed e o placar do replay: o que muda é só o relógio (tempo real, atrasado) e a rota,
que aqui é uma linha direta entre a sonda e o destino. Nada é recalculado na página; este módulo só repete o que o motor
já tem. Datas em segundos desde 1970 (UTC), como no replay.
"""

import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from preditor import config
from preditor.aovivo import parametros
from preditor.visualizacao.exportacao import ExportadorReplay
from preditor.visualizacao.rotas import Geografia

FORMATO_INSTANTE = "%Y-%m-%dT%H:%M:%SZ"


def _cruza_o_corte(a: list[float], b: list[float]) -> bool:
    """O círculo máximo de `a` a `b` atravessa a borda do mapa (o meridiano oposto ao centro)? Pontos [lon, lat], em graus."""
    va, vb = (_vetor(ponto) for ponto in (a, b))
    angulo = math.acos(max(-1.0, min(1.0, float(np.dot(va, vb)))))
    if angulo < 1e-9:
        return False
    longitudes = []
    for i in range(parametros.PONTOS_PARA_CHECAR_O_CORTE + 1):
        fracao = i / parametros.PONTOS_PARA_CHECAR_O_CORTE
        # Interpolação esférica: o ponto a `fracao` do caminho, sobre o círculo máximo.
        ponto = (math.sin((1 - fracao) * angulo) * va + math.sin(fracao * angulo) * vb) / math.sin(angulo)
        longitudes.append(math.degrees(math.atan2(ponto[1], ponto[0])))
    # Posição horizontal no mapa: a longitude medida do centro, em [-180, 180). Um salto maior que 180° entre amostras vizinhas é
    # a linha atravessando a borda.
    x = [((lon - parametros.CENTRO_DO_MAPA_AO_VIVO + 180) % 360) - 180 for lon in longitudes]
    return any(abs(x[i + 1] - x[i]) > 180 for i in range(len(x) - 1))


def _vetor(ponto: list[float]) -> np.ndarray:
    lon, lat = math.radians(ponto[0]), math.radians(ponto[1])
    return np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])


def _caminho_sem_corte(sonda: list[float], destino: list[float]) -> list[list[float]]:
    """A linha direta, ou, se ela cruzaria a borda do mapa, a volta pelo outro lado do mundo com um ponto no meio."""
    if not _cruza_o_corte(sonda, destino):
        return [sonda, destino]
    # A diferença de longitude mais curta vai de -180 a 180; a volta pelo outro lado é a que sobra para fechar 360°.
    curta = ((destino[0] - sonda[0] + 540) % 360) - 180
    longa = curta - math.copysign(360, curta)
    meio = [round(sonda[0] + longa / 2, config.CASAS_COORDENADA), round((sonda[1] + destino[1]) / 2, config.CASAS_COORDENADA)]
    meio[0] = round(((meio[0] + 180) % 360) - 180, config.CASAS_COORDENADA)  # a longitude volta para [-180, 180]
    caminho = [sonda, meio, destino]
    assert not any(_cruza_o_corte(a, b) for a, b in zip(caminho, caminho[1:])), f"a volta de {sonda} a {destino} ainda cruza o corte"
    return caminho


def _instante(segundos: int) -> str:
    return datetime.fromtimestamp(segundos, tz=timezone.utc).strftime(FORMATO_INSTANTE)


def _fluxo(fluxo_id: str, ficha: pd.Series, sonda: dict) -> dict:
    """Um fluxo para o mapa: a linha direta da sonda ao destino, com o km e o RTT mínimo teórico dela."""
    prb_id, _, msm_id = fluxo_id.split("|")
    destino = parametros.DESTINOS[int(msm_id)]
    ponto_sonda = [round(sonda["longitude"], config.CASAS_COORDENADA), round(sonda["latitude"], config.CASAS_COORDENADA)]
    ponto_destino = [round(coordenada, config.CASAS_COORDENADA) for coordenada in destino["ponto"]]
    caminho = _caminho_sem_corte(ponto_sonda, ponto_destino)
    # km da rota = a soma dos pedaços do caminho desenhado (um só, na linha direta; dois, se ela dá a volta pelo outro lado).
    km = round(Geografia.comprimento_km(caminho), config.CASAS_KM)
    # O RTT mínimo teórico é o que a física permite: vem da MENOR distância (o círculo máximo), mesmo quando a linha desenhada dá a
    # volta pelo outro lado do mundo (o cartão da página promete "o mínimo que a física permite").
    km_minimo = Geografia.distancia_km(ponto_sonda, ponto_destino)
    return {
        "id": fluxo_id,
        "regiao": destino["regiao"],
        "pais": destino["pais"],
        "origem_pais": sonda["pais"],  # a página mostra o país da sonda (no replay ele é sempre o Brasil)
        "opcao": parametros.OPCAO_DA_ROTA_DIRETA,
        "km": km,
        "rtt_minimo_ms": round(Geografia.rtt_minimo_ms(km_minimo), config.CASAS_RTT_REPLAY),
        # Todo fluxo que chega aqui tem baseline suficiente, logo mediana: o `None` da página (sem referência) não ocorre.
        "mediana_ms": round(float(ficha["mediana"]), config.CASAS_RTT_REPLAY),
        "trechos": [
            {
                "tipo": "direto",
                "nome": parametros.NOME_DO_TRECHO_DIRETO,
                "km": km,
                "nos": [
                    {"tipo": "sonda", "nome": f"sonda {prb_id}", "ponto": ponto_sonda},
                    {"tipo": "destino", "nome": f"{destino['cidade']} ({destino['dst_addr']})", "ponto": ponto_destino},
                ],
                "caminho": caminho,
            }
        ],
    }


def recortar(calculado: pd.DataFrame) -> pd.DataFrame:
    """As medições das últimas `HORAS_NA_PAGINA` horas (a contar da mais recente): é o que a página recebe."""
    limite = int(calculado["t"].max()) - parametros.HORAS_NA_PAGINA * 3600
    return calculado[calculado["t"] >= limite]


def montar_fluxos(estado: dict, ficha: pd.DataFrame) -> list[dict]:
    """Os fluxos com ficha utilizável, em ordem alfabética do `fluxo_id` (o `f` das medições é a posição nesta lista)."""
    utilizaveis = ficha[~ficha["baseline_insuficiente"]]
    return [_fluxo(fluxo_id, utilizaveis.loc[fluxo_id], estado["sondas"][fluxo_id.split("|")[0]]) for fluxo_id in sorted(utilizaveis.index)]


def fluxos_impossiveis(fluxos: list[dict]) -> list[str]:
    """Fluxos cuja mediana medida é MENOR que o RTT mínimo da física: a coordenada da sonda ou do destino está errada, ou o IP é anycast."""
    return [fluxo["id"] for fluxo in fluxos if fluxo["mediana_ms"] < fluxo["rtt_minimo_ms"]]


def montar(calculado: pd.DataFrame, previsoes: dict, estado: dict, ficha: pd.DataFrame, modelo: dict, agora: int) -> dict:
    """O documento completo. `calculado` vem de `Rotulo.rotular`; `previsoes` é (fluxo_id, t) → classe prevista (congelada)."""
    fluxos = montar_fluxos(estado, ficha)
    posicao = {fluxo["id"]: i for i, fluxo in enumerate(fluxos)}

    ordenado = recortar(calculado).sort_values(["t", "fluxo_id"], kind="stable")
    medicoes = []
    for linha in ordenado.itertuples(index=False):
        conferivel = isinstance(linha.status_futuro, str)
        medicoes.append(
            {
                "f": posicao[linha.fluxo_id],
                "t": int(linha.t),
                "rtt": None if pd.isna(linha.rtt) else round(float(linha.rtt), config.CASAS_RTT_REPLAY),
                "timeout": int(linha.timeout_atual),
                "atual": linha.status_atual,
                "previsto": previsoes[(linha.fluxo_id, int(linha.t))],
                # Sem a 3ª medição seguinte (ou fora de 10 a 14 min) o futuro é nulo: ainda não dá para conferir.
                "futuro": linha.status_futuro if conferivel else None,
                "conferivel": conferivel,
                "t_futuro": int(linha.t_futuro) if conferivel else None,
            }
        )
    return {
        "meta": {
            "bloco": "ao_vivo",
            "modo": "ao_vivo",
            "inicio": _instante(medicoes[0]["t"]),
            "fim": _instante(medicoes[-1]["t"]),
            "inicio_ao_vivo": _instante(estado["t0"]),  # T0: o baseline termina aqui e nada de antes dele entra no X
            "gerado_em": _instante(agora),
            "gerado_em_s": agora,
            "atraso_s": parametros.ATRASO_DA_PAGINA_S,
            "atualizacao_s": parametros.ATUALIZACAO_DA_PAGINA_S,
            "janela_h": parametros.HORAS_NA_PAGINA,
            "intervalo_s": parametros.INTERVALO_CONSULTA_S,
            "classes": list(config.CLASSES),
            "aviso": parametros.AVISO_ROTA_DIRETA,
        },
        "modelo": modelo,
        "fluxos": fluxos,
        "medicoes": medicoes,
    }


def gravar(documento: dict) -> None:
    """Grava por um arquivo temporário e renomeia: a página nunca lê um JSON pela metade."""
    parametros.ARQUIVO_PAGINA.parent.mkdir(parents=True, exist_ok=True)
    temporario = parametros.ARQUIVO_PAGINA.with_suffix(".json.tmp")
    temporario.write_text(ExportadorReplay.texto(documento), encoding="utf-8")
    temporario.replace(parametros.ARQUIVO_PAGINA)
