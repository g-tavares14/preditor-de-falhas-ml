"""Geografia e sondas do serviço ao vivo: distância em círculo máximo, RTT mínimo teórico e as coordenadas das sondas.

Cópia mínima de `preditor_analise/visualizacao/rotas.py` (`Geografia` e `Sondas.ler`): o serviço não importa o código de
análise, só o `config`. Tudo em [longitude, latitude].
"""

import math

import pandas as pd

from preditor_analise import config


class Geografia:
    @staticmethod
    def distancia_km(a: list[float], b: list[float]) -> float:
        """Distância em círculo máximo entre dois pontos [lon, lat] (fórmula de haversine)."""
        lon_a, lat_a = math.radians(a[0]), math.radians(a[1])
        lon_b, lat_b = math.radians(b[0]), math.radians(b[1])
        # O haversine usa só a diferença de longitude dentro de um seno: 170° e -170° dão 20°, sem "desdobrar" nada.
        parte = (
            math.sin((lat_b - lat_a) / 2) ** 2
            + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
        )
        return 2 * config.RAIO_TERRA_KM * math.asin(math.sqrt(parte))

    @staticmethod
    def comprimento_km(caminho: list[list[float]]) -> float:
        """Soma das distâncias entre pontos consecutivos do caminho."""
        return sum(Geografia.distancia_km(a, b) for a, b in zip(caminho, caminho[1:]))

    @staticmethod
    def rtt_minimo_ms(km: float) -> float:
        """RTT mínimo teórico na fibra: ida e volta, a ~200 km por ms (`config.VELOCIDADE_FIBRA_KM_POR_MS`)."""
        return 2 * km / config.VELOCIDADE_FIBRA_KM_POR_MS


class Sondas:
    @staticmethod
    def ler() -> dict[int, list[float]]:
        """`prb_id` → [lon, lat], lido do CSV versionado. Sem o arquivo, pede o script que o gera (a coleta precisa de rede)."""
        if not config.ARQUIVO_SONDAS.exists():
            raise SystemExit(
                f"Não encontrei {config.ARQUIVO_SONDAS}.\nRode antes: uv run python -m preditor_analise.visualizacao.coletar_sondas"
            )
        tabela = pd.read_csv(config.ARQUIVO_SONDAS)
        assert tabela["prb_id"].is_unique, f"prb_id repetido em {config.ARQUIVO_SONDAS.name}"
        assert tabela[["longitude", "latitude"]].notna().all().all(), f"sonda sem coordenada em {config.ARQUIVO_SONDAS.name}"
        assert tabela["longitude"].between(-180, 180).all() and tabela["latitude"].between(-90, 90).all(), (
            f"coordenada inválida em {config.ARQUIVO_SONDAS.name}"
        )
        return {int(linha.prb_id): [float(linha.longitude), float(linha.latitude)] for linha in tabela.itertuples()}
