"""Etapa 2: a "ficha" de cada fluxo — o que é normal para ele.

Calculada SÓ com o Período A e depois congelada. É ela que faz o "normal"
mudar por região: BR→BR tem mediana ~9 ms, BR→Japão ~278 ms.
"""

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from preditor import config


def mediana(coluna: str) -> Column:
    """Mediana exata: ordena os valores e pega o do meio (ignora nulos)."""
    return F.expr(f"percentile({coluna}, 0.5)")


class Baseline:
    def calcular(self, medicoes: DataFrame) -> DataFrame:
        periodo_a = medicoes.filter(F.col("periodo") == "A")
        ficha = self._estatisticas(periodo_a)
        ficha = ficha.join(self._mad(periodo_a, ficha), "fluxo_id", "left")
        return self._aplicar_piso(ficha)

    @staticmethod
    def _estatisticas(periodo_a: DataFrame) -> DataFrame:
        """Uma linha por fluxo com as estatísticas básicas do Período A."""
        # groupBy + agg = o "GROUP BY" do SQL: junta as linhas de cada fluxo.
        # count("rtt") conta só os não nulos, ou seja, os RTT válidos.
        return (
            periodo_a.groupBy("fluxo_id", "rota", "destination_country")
            .agg(
                F.count("*").alias("n_medicoes"),
                F.count("rtt").alias("n_validos"),
                mediana("rtt").alias("mediana"),
                F.expr("percentile(rtt, 0.75) - percentile(rtt, 0.25)").alias("iqr"),
                mediana("jitter").alias("jitter_tipico"),
                mediana("perda_pct").alias("perda_tipica"),
            )
            .withColumn("prop_resposta", F.col("n_validos") / F.col("n_medicoes"))
        )

    @staticmethod
    def _mad(periodo_a: DataFrame, ficha: DataFrame) -> DataFrame:
        """MAD = mediana de |RTT − mediana|: quanto o fluxo costuma variar.

        Precisa de duas passadas: primeiro a mediana (em `ficha`), depois a
        distância de cada RTT até ela.
        """
        return (
            periodo_a.filter(F.col("rtt").isNotNull())
            .join(ficha.select("fluxo_id", "mediana"), "fluxo_id")
            .withColumn("distancia", F.abs(F.col("rtt") - F.col("mediana")))
            .groupBy("fluxo_id")
            .agg(mediana("distancia").alias("mad"))
        )

    @staticmethod
    def _aplicar_piso(ficha: DataFrame) -> DataFrame:
        """Fluxo com menos de 1.500 RTT válidos fica sem mediana (não inventamos)."""
        insuficiente = F.col("n_validos") < config.PISO_RTT_VALIDOS
        return (
            ficha.withColumn("baseline_insuficiente", insuficiente)
            .withColumn("mediana", F.when(~insuficiente, F.col("mediana")))
            .withColumn("mad", F.when(~insuficiente, F.col("mad")))
        )

    @staticmethod
    def escala_robusta() -> Column:
        """A "unidade de variação" do fluxo, usada para calcular o z robusto.

        Normalmente 1,4826 × MAD. Se MAD = 0 (fluxo perfeitamente constante),
        a divisão explodiria; a RFC manda usar max(IQR / 1,349, 1 ms).
        """
        return F.when(F.col("mad") > 0, config.FATOR_MAD * F.col("mad")).otherwise(
            F.greatest(F.col("iqr") / config.FATOR_IQR, F.lit(config.ESCALA_MINIMA_MS))
        )
