"""Etapa 1: transformar a tabela bruta em uma linha por medição.

Cada linha da tabela do RIPE Atlas é uma *medição*: uma rajada de 3 pings de
uma probe para um destino, num instante. Os pings vêm dentro de uma lista
(`pings`). Aqui resumimos essa lista em números simples: RTT, jitter e perda.
"""

from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F

from preditor import config


class Medicoes:
    def __init__(self, spark: SparkSession):
        self.spark = spark

    def carregar(self) -> DataFrame:
        """Lê o BigQuery e devolve as medições prontas (etapa completa)."""
        return self.transformar(self.ler_bigquery())

    def ler_bigquery(self) -> DataFrame:
        # O Spark é "preguiçoso": isto só descreve a leitura. Os dados só são
        # baixados quando algo precisar do resultado (um write, count, show...).
        return (
            self.spark.read.format("bigquery")
            .option("parentProject", config.PROJECT)
            .option("location", config.LOCATION)
            .load(config.TABLE)
        )

    def transformar(self, bruto: DataFrame) -> DataFrame:
        df = (
            bruto
            # rtts = lista só com os RTT válidos da rajada.
            # Atenção: no RIPE Atlas o ping que deu timeout vem com rtt = 0.0,
            # então "RTT válido" é rtt > 0 E timeout = false.
            .withColumn(
                "rtts",
                F.expr(
                    "transform("
                    "  filter(pings, p -> p.rtt > 0 AND NOT coalesce(p.timeout, false)),"
                    "  p -> p.rtt)"
                ),
            )
            .withColumn("n_resp", F.size("rtts"))  # quantos pings responderam
        )

        return (
            df.select(
                # Um fluxo = uma série temporal: probe + destino + medição do Atlas.
                F.concat_ws("|", "prb_id", "dst_addr", "msm_id").alias("fluxo_id"),
                "prb_id",
                "dst_addr",
                "msm_id",
                # Metadados de região: servem para relatório, NÃO entram no modelo.
                F.concat(F.lit(f"{config.ORIGEM}→"), "destination_region").alias("rota"),
                "destination_country",
                "destination_region",
                F.col("start_time").alias("t"),
                self._rtt().alias("rtt"),
                self._jitter().alias("jitter"),
                self._perda_pct().alias("perda_pct"),
            )
            # timeout_atual = 1 quando a medição inteira ficou sem resposta.
            .withColumn(
                "timeout_atual",
                (F.col("rtt").isNull() | (F.col("perda_pct") == 100)).cast("int"),
            )
            .transform(self._marcar_periodo)
        )

    # --- Cálculos de cada coluna -------------------------------------------------

    @staticmethod
    def _rtt() -> Column:
        """RTT da medição = média dos pings válidos (campo `avg` do Atlas).

        Sem nenhum ping válido, fica nulo (nunca 0: 0 ms seria um RTT falso).
        """
        return F.when(F.col("n_resp") > 0, F.expr("aggregate(rtts, 0D, (soma, x) -> soma + x)") / F.col("n_resp"))

    @staticmethod
    def _jitter() -> Column:
        """Jitter = média da diferença entre pings consecutivos (RFC 3550).

        Ex.: RTTs [10, 12, 11] → |12-10| + |11-12| = 3 → 3 / 2 = 1,5 ms.
        Precisa de pelo menos 2 respostas; senão fica nulo.
        """
        soma_diferencas = F.expr(
            "aggregate(sequence(1, n_resp - 1), 0D, (soma, i) -> soma + abs(rtts[i] - rtts[i - 1]))"
        )
        return F.when(F.col("n_resp") >= 2, soma_diferencas / (F.col("n_resp") - 1))

    @staticmethod
    def _perda_pct() -> Column:
        """Perda = pacotes que não voltaram, em %. Com 3 pacotes: 0, 33, 67 ou 100."""
        return (F.col("packets_sent") - F.col("packets_received")) / F.col("packets_sent") * 100

    @staticmethod
    def _marcar_periodo(df: DataFrame) -> DataFrame:
        """Coluna `periodo`: "A" nas primeiras 108 h da tabela, "B" no resto."""
        # O início (t0) é calculado dentro do Spark, não no Python, para não
        # sofrer conversão de fuso horário.
        inicio = df.agg(F.min("t").alias("t0"))
        corte = F.col("t0") + F.expr(f"INTERVAL {config.HORAS_PERIODO_A} HOURS")
        return (
            df.crossJoin(inicio)  # cola t0 em todas as linhas
            .withColumn("periodo", F.when(F.col("t") < corte, "A").otherwise("B"))
            .drop("t0")
        )
