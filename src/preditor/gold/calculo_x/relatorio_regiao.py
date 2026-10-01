"""Relatório: os limites da regra traduzidos para ms, por região.

Não é usado pelo modelo. Serve para mostrar (e auditar) que o mesmo limiar
relativo vira valores em ms bem diferentes em cada rota.
"""

import csv
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from preditor import config
from preditor.gold.calculo_x.baseline import Baseline, mediana


class RelatorioRegiao:
    def limites(self, baseline: DataFrame) -> DataFrame:
        escala = Baseline.escala_robusta()
        # Conta ao contrário do z: z = (RTT − mediana) / escala
        #                     → RTT = mediana + z × escala
        por_fluxo = baseline.filter(~F.col("baseline_insuficiente")).select(
            "rota",
            "destination_country",
            "mediana",
            (F.col("mediana") + config.Z_RISCO * escala).alias("lim_risco_z2_ms"),
            (F.col("mediana") + config.Z_FALHA * escala).alias("lim_falha_z35_ms"),
            (F.col("mediana") * (1 + config.AUMENTO_RISCO_PCT / 100)).alias("lim_aumento30_ms"),
            (F.col("mediana") * (1 + config.AUMENTO_FALHA_PCT / 100)).alias("lim_aumento80_ms"),
        )

        # Cada rota tem ~13 fluxos (um por probe); resumimos pela mediana deles.
        valores = [c for c in por_fluxo.columns if c not in ("rota", "destination_country")]
        return (
            por_fluxo.groupBy("rota", "destination_country")
            .agg(F.count("*").alias("fluxos"), *[F.round(mediana(c), 1).alias(c) for c in valores])
            .orderBy("mediana")
        )

    @staticmethod
    def salvar_csv(df: DataFrame, caminho: Path) -> None:
        # São ~6 linhas: trazemos para o Python (collect) e gravamos um CSV
        # simples, em vez de deixar o Spark criar uma pasta de arquivos.
        with caminho.open("w", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(df.columns)
            escritor.writerows(df.collect())
