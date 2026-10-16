"""O motor de cálculo do serviço ao vivo, em pandas: baseline, X e Y (SPEC-ao-vivo.md).

É a cópia, sem Spark, das fórmulas de `gold/calculo_x/baseline.py`, `gold/calculo_x/features.py` e
`gold/calculo_y/rotulo.py`. Cada função diz de onde veio. Os limiares (z, aumento, janela, piso, 1.500 RTT) são lidos de
`config`, nunca copiados. A cópia é conferida contra o Gold em `conferencia.py`: se o Spark mudar e esta cópia não, a
conferência para o serviço antes de ele prever.

Entrada: um DataFrame com uma linha por medição e as colunas do Silver (`fluxo_id`, `t`, `rtt`, `jitter`, `perda_pct`,
`timeout_atual`), com `t` em segundos desde 1970 (inteiro) ou em `datetime`. Valor ausente fica `NaN` e nada é imputado.
"""

import numpy as np
import pandas as pd

from preditor import config

COLUNAS_FICHA = ["mediana", "mad", "iqr", "jitter_tipico"]


def _para_segundos(t: pd.Series) -> pd.Series:
    """`t` em segundos desde 1970, seja ele inteiro (a API) ou `datetime` (o Silver)."""
    if pd.api.types.is_datetime64_any_dtype(t):
        return (t - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)
    return t.astype("int64")


class Baseline:
    @staticmethod
    def calcular(periodo_a: pd.DataFrame) -> pd.DataFrame:
        """A ficha de cada fluxo (índice = `fluxo_id`) a partir das medições do Período A (`baseline.py`).

        `median` e `quantile` do pandas ignoram o nulo e interpolam linearmente, como o `percentile` exato do Spark.
        """
        por_fluxo = periodo_a.groupby("fluxo_id")
        ficha = pd.DataFrame(
            {
                "n_medicoes": por_fluxo.size(),
                "n_validos": por_fluxo["rtt"].count(),  # `count` só conta o não nulo: os RTT válidos
                "mediana": por_fluxo["rtt"].median(),
                "iqr": por_fluxo["rtt"].quantile(0.75) - por_fluxo["rtt"].quantile(0.25),
                "jitter_tipico": por_fluxo["jitter"].median(),
                "perda_tipica": por_fluxo["perda_pct"].median(),
            }
        )
        # MAD = mediana de |RTT − mediana|, só nas medições com RTT (a distância de um RTT nulo é nula e fica de fora).
        distancia = (periodo_a["rtt"] - periodo_a["fluxo_id"].map(ficha["mediana"])).abs()
        ficha["mad"] = distancia.groupby(periodo_a["fluxo_id"]).median()
        # Menos de 1.500 RTT válidos: sem mediana nem MAD (não inventamos), como `_aplicar_piso`.
        ficha["baseline_insuficiente"] = ficha["n_validos"] < config.PISO_RTT_VALIDOS
        ficha.loc[ficha["baseline_insuficiente"], ["mediana", "mad"]] = np.nan
        return ficha

    @staticmethod
    def escala_robusta(ficha: pd.DataFrame) -> pd.Series:
        """A "unidade de variação" do fluxo: 1,4826 × MAD; se MAD = 0, max(IQR / 1,349, 1 ms) (RFC §8.4)."""
        return pd.Series(
            np.where(ficha["mad"] > 0, config.FATOR_MAD * ficha["mad"], np.maximum(ficha["iqr"] / config.FATOR_IQR, config.ESCALA_MINIMA_MS)),
            index=ficha.index,
        )


class Features:
    @staticmethod
    def construir(medicoes: pd.DataFrame, ficha: pd.DataFrame) -> pd.DataFrame:
        """O X de cada medição, comparada com a ficha do SEU fluxo (`features.py`). Fluxo sem ficha utilizável fica de fora.

        Devolve as medições ordenadas por (`fluxo_id`, `t`), com índice novo, e as colunas do X mais as auxiliares
        (`moderado`, `desviado`) que o Y e a janela usam.
        """
        utilizaveis = ficha[~ficha["baseline_insuficiente"]]
        df = medicoes[medicoes["fluxo_id"].isin(utilizaveis.index)].copy()
        df["t"] = _para_segundos(df["t"])
        df = df.sort_values(["fluxo_id", "t"], kind="stable").reset_index(drop=True)

        # Cola a ficha do fluxo em cada medição (o `join` do Spark).
        df["mediana"] = df["fluxo_id"].map(utilizaveis["mediana"])
        df["jitter_tipico"] = df["fluxo_id"].map(utilizaveis["jitter_tipico"])
        df["escala"] = df["fluxo_id"].map(Baseline.escala_robusta(utilizaveis))
        df["mad_zero"] = df["fluxo_id"].map(utilizaveis["mad"]) == 0

        Features._metricas_da_medicao(df)
        Features._metricas_da_janela(df)
        return df.drop(columns=["mediana", "jitter_tipico", "escala", "mad_zero"])

    @staticmethod
    def _metricas_da_medicao(df: pd.DataFrame) -> None:
        """`aumento_pct`, `z_robusto` e `jitter_relativo` (olhando só a medição atual)."""
        desvio = df["rtt"] - df["mediana"]  # quantos ms acima do normal; nulo sem RTT
        df["aumento_pct"] = desvio / df["mediana"] * 100
        # z = desvio / escala. MAD = 0 com desvio 0 vale 0 (o `when` do Spark); sem RTT o z é nulo.
        z = desvio / df["escala"]
        z = z.mask(df["mad_zero"] & (desvio == 0), 0.0)
        df["z_robusto"] = z.where(df["rtt"].notna())

        jitter, tipico = df["jitter"], df["jitter_tipico"]
        with np.errstate(divide="ignore", invalid="ignore"):
            razao = jitter / tipico
        # Típico 0: se o atual também é 0, está normal (1); se não, conta como alto (JITTER_RISCO). Sem jitter, nulo.
        razao = pd.Series(np.where(tipico == 0, np.where(jitter == 0, 1.0, config.JITTER_RISCO), razao), index=df.index)
        df["jitter_relativo"] = razao.where(jitter.notna())

    @staticmethod
    def _metricas_da_janela(df: pd.DataFrame) -> None:
        """As colunas das últimas `JANELA` medições do MESMO fluxo (a atual e as anteriores; nunca o futuro)."""
        z, aumento = df["z_robusto"], df["aumento_pct"]
        jitter_relativo = df["jitter_relativo"]
        # Comparação com nulo dá falso no pandas, como o `coalesce(nulo, falso)` do Spark (`_flag`).
        moderado = ((z >= config.Z_RISCO) & (z < config.Z_FALHA)) | aumento.between(config.AUMENTO_RISCO_PCT, config.AUMENTO_FALHA_PCT) | (
            jitter_relativo >= config.JITTER_RISCO
        )
        df["moderado"] = moderado.astype(int)
        df["desviado"] = ((z >= config.Z_RISCO) | (aumento >= config.AUMENTO_RISCO_PCT) | (df["timeout_atual"] == 1)).astype(int)
        # `aumento > 80` é nulo onde não há RTT: soma e média ignoram o nulo e, sem nenhum valor na janela, ficam nulas.
        aumento80 = (aumento > config.AUMENTO_FALHA_PCT).astype(float).where(aumento.notna())

        def janela(serie: pd.Series, funcao: str) -> pd.Series:
            """`rowsBetween(-(JANELA-1), 0)` do Spark: `min_periods=1` aceita as primeiras linhas, com janela menor."""
            rolante = serie.groupby(df["fluxo_id"]).rolling(config.JANELA, min_periods=1)
            return getattr(rolante, funcao)().reset_index(level=0, drop=True).sort_index()

        df["n5_timeout"] = janela(df["timeout_atual"].astype(float), "sum")
        df["n5_aumento80"] = janela(aumento80, "sum")
        df["n5_moderado"] = janela(df["moderado"].astype(float), "sum")
        df["min5_z"] = janela(z, "min")
        df["media5_z"] = janela(z, "mean")


class Rotulo:
    @staticmethod
    def rotular(df: pd.DataFrame) -> pd.DataFrame:
        """Acrescenta `regra` (1 a 6), `status_atual`, `status_futuro` e `t_futuro` (`rotulo.py`). `df` vem de `Features.construir`."""
        # A tabela da RFC §8.4 na ordem: a primeira linha verdadeira decide. Comparação com nulo é falsa, como no Spark.
        falha_por_z = df["z_robusto"] >= config.Z_FALHA
        if config.PISO_AUMENTO_FALHA_PCT is not None:  # linha 3 com piso (SPEC-piso-regra3.md)
            falha_por_z = falha_por_z & (df["aumento_pct"] >= config.PISO_AUMENTO_FALHA_PCT)
        condicoes = [
            df["perda_pct"] >= config.PERDA_FALHA_PCT,
            df["n5_timeout"] >= config.N5_TIMEOUT_FALHA,
            falha_por_z,
            df["n5_aumento80"] >= config.N5_AUMENTO80_FALHA,
            (df["moderado"] == 1) & (df["n5_moderado"] >= config.N5_RISCO),
        ]
        df["regra"] = np.select(condicoes, [1, 2, 3, 4, 5], default=6)
        df["status_atual"] = np.select([df["regra"] <= 4, df["regra"] == 5], ["FALHA", "RISCO"], default="OK")

        # O futuro: o `status_atual` da 3ª medição seguinte do mesmo fluxo, só se ela vier de 600 a 840 s depois (RFC §3).
        por_fluxo = df.groupby("fluxo_id")
        status_depois = por_fluxo["status_atual"].shift(-config.PASSOS_FUTURO)
        t_depois = por_fluxo["t"].shift(-config.PASSOS_FUTURO)
        segundos = t_depois - df["t"]
        no_prazo = segundos.between(config.FUTURO_MIN_S, config.FUTURO_MAX_S)
        df["status_futuro"] = status_depois.where(no_prazo)
        df["t_futuro"] = t_depois.where(no_prazo)
        return df
