"""Camada Gold, cálculo do X: as features (o X do modelo) no Período B.

Cada medição do Período B é comparada com a ficha congelada do SEU fluxo.
Por isso as features são relativas ("quanto piorou em relação ao normal
deste fluxo") e não absolutas ("quantos ms"). É assim que um mesmo modelo
serve para BR→BR e para BR→Japão.
"""

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

from preditor import config
from preditor.gold.calculo_x.baseline import Baseline


class Features:
    def construir(self, medicoes: DataFrame, baseline: DataFrame) -> DataFrame:
        colunas_ficha = ["mediana", "mad", "iqr", "jitter_tipico"]
        ficha = baseline.filter(~F.col("baseline_insuficiente")).select("fluxo_id", *colunas_ficha)
        # join = cola a ficha do fluxo em cada medição do Período B.
        # Fluxos sem ficha (insuficientes) somem aqui, como manda a RFC.
        periodo_b = medicoes.filter(F.col("periodo") == "B").join(ficha, "fluxo_id")

        return (
            periodo_b.transform(self._metricas_da_medicao)
            .transform(self._metricas_da_janela)
            # A ficha já cumpriu seu papel; tirar evita confundir com features.
            .drop(*colunas_ficha)
        )

    # --- Olhando só para a medição atual ------------------------------------------

    def _metricas_da_medicao(self, df: DataFrame) -> DataFrame:
        desvio = F.col("rtt") - F.col("mediana")  # quantos ms acima do normal
        return (
            df.withColumn("latencia_relativa", F.col("rtt") / F.col("mediana"))  # 1,0 = normal
            .withColumn("aumento_pct", desvio / F.col("mediana") * 100)
            .withColumn("z_robusto", self._z_robusto(desvio))
            .withColumn("jitter_relativo", self._jitter_relativo())
        )

    @staticmethod
    def _z_robusto(desvio: Column) -> Column:
        """z = desvio / unidade de variação. Ex.: z = 3 → 3 "unidades" acima do normal.

        Sem RTT (timeout) o z fica nulo: não há o que comparar.
        """
        mad_zero_e_igual = (F.col("mad") == 0) & (desvio == 0)
        return F.when(
            F.col("rtt").isNotNull(),
            F.when(mad_zero_e_igual, F.lit(0.0)).otherwise(desvio / Baseline.escala_robusta()),
        )

    @staticmethod
    def _jitter_relativo() -> Column:
        """Jitter atual / jitter típico. Casos especiais da RFC quando o típico é 0."""
        return F.when(
            F.col("jitter").isNotNull(),
            F.when(
                F.col("jitter_tipico") == 0,
                # Típico 0: se o atual também é 0, está normal (1); se não, conta como alto (3).
                F.when(F.col("jitter") == 0, F.lit(1.0)).otherwise(F.lit(config.JITTER_RISCO)),
            ).otherwise(F.col("jitter") / F.col("jitter_tipico")),
        )

    # --- Olhando para as últimas 5 medições do fluxo ------------------------------

    def _metricas_da_janela(self, df: DataFrame) -> DataFrame:
        # Uma "janela" do Spark: para cada linha, enxerga as 4 medições
        # anteriores do MESMO fluxo, em ordem de tempo, mais a atual.
        # rowsBetween(-4, 0) garante que nunca olhamos para o futuro.
        ultimas = (
            Window.partitionBy("fluxo_id").orderBy("t").rowsBetween(-(config.JANELA - 1), 0)
        )
        return (
            df.withColumn("moderado", self._flag(self._desvio_moderado()))
            .withColumn("desviado", self._flag(self._desvio_qualquer()))
            .withColumn("n5_timeout", F.sum("timeout_atual").over(ultimas))
            .withColumn(
                "n5_aumento80",
                F.sum((F.col("aumento_pct") > config.AUMENTO_FALHA_PCT).cast("int")).over(ultimas),
            )
            .withColumn("n5_moderado", F.sum("moderado").over(ultimas))
            # Tendência: RTT atual vs. média recente, em fração da mediana.
            # Positivo = subindo; negativo = descendo.
            .withColumn("tendencia", (F.col("rtt") - F.avg("rtt").over(ultimas)) / F.col("mediana"))
            # Persistência: fração (0 a 1) das últimas 5 com algum desvio.
            .withColumn("persistencia", F.avg("desviado").over(ultimas))
        )

    @staticmethod
    def _desvio_moderado() -> Column:
        """Critério de RISCO da RFC (linha 5), só para a medição atual."""
        return (
            ((F.col("z_robusto") >= config.Z_RISCO) & (F.col("z_robusto") < config.Z_FALHA))
            | F.col("aumento_pct").between(config.AUMENTO_RISCO_PCT, config.AUMENTO_FALHA_PCT)
            | (F.col("jitter_relativo") >= config.JITTER_RISCO)
        )

    @staticmethod
    def _desvio_qualquer() -> Column:
        """Qualquer sinal de problema: moderado, extremo ou timeout."""
        return (
            (F.col("z_robusto") >= config.Z_RISCO)
            | (F.col("aumento_pct") >= config.AUMENTO_RISCO_PCT)
            | (F.col("timeout_atual") == 1)
        )

    @staticmethod
    def _flag(condicao: Column) -> Column:
        """Condição → 0/1. Comparação com nulo dá nulo; aqui nulo vira 0."""
        return F.coalesce(condicao, F.lit(False)).cast("int")
