"""Ponto de entrada: `uv run python -m preditor [camada]`.

Sem argumento: Bronze (BigQuery → Parquet) → Silver (medições) → Gold (baseline do
Período A e features do Período B). Com `bronze`: só a ingestão do BigQuery.
Com `silver`: só a normalização, lendo o Bronze do disco (sem rede).
Com `gold`: só baseline e features, lendo o Silver do disco (sem rede).
Cada camada lê a anterior do disco, nunca da memória.
"""

import argparse
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from preditor import config
from preditor.bronze.ingestao import Bronze
from preditor.gold.calculo_x.baseline import Baseline
from preditor.gold.calculo_x.features import Features
from preditor.gold.calculo_x.relatorio_regiao import RelatorioRegiao
from preditor.silver.medicao import Medicoes
from preditor.spark import build_spark


class Pipeline:
    def __init__(self, spark: SparkSession):
        self.spark = spark

    def executar_bronze(self) -> None:
        """Baixa a tabela do BigQuery e grava o Bronze, conferindo o resultado."""
        linhas_bigquery, colunas_bigquery = Bronze(self.spark).ingerir()
        self._verificar_bronze(linhas_bigquery, colunas_bigquery)

    def executar_silver(self) -> None:
        """Lê o Bronze do disco, normaliza as medições e grava o Silver, conferindo o resultado."""
        # Só lê Parquet local: não toca o BigQuery nem usa `Bronze.ingerir`.
        bronze = self._ler_camada(config.ARQUIVO_BRONZE, "bronze")
        config.SILVER.mkdir(parents=True, exist_ok=True)
        Medicoes().transformar(bronze).write.mode("overwrite").parquet(str(config.ARQUIVO_SILVER))
        self._verificar_silver()

    def executar_gold(self) -> None:
        """Lê o Silver do disco, calcula baseline e features, grava o Gold, conferindo o resultado."""
        # Lê as medições do Silver gravado em disco, não da memória da etapa anterior.
        # .cache() guarda o resultado em memória: medições e baseline são
        # usados várias vezes abaixo e não queremos reler o Parquet a cada uso.
        # Sem Silver no disco, `_ler_camada` termina mandando rodar `silver` antes.
        medicoes = self._ler_camada(config.ARQUIVO_SILVER, "silver").cache()
        baseline = Baseline().calcular(medicoes).cache()
        features = Features().construir(medicoes, baseline)

        features = self._salvar(baseline, features)
        self._relatorio(baseline)
        self._verificar_gold(medicoes, baseline, features)

    def _ler_camada(self, arquivo: Path, camada_anterior: str) -> DataFrame:
        """Lê o Parquet de uma camada ou termina com uma mensagem dizendo o que rodar antes."""
        if not arquivo.exists():
            # SystemExit com texto: o Python imprime a mensagem em stderr e sai com
            # código 1, sem traceback. Nunca recai no BigQuery.
            raise SystemExit(
                f"Não encontrei {arquivo}.\n"
                f"Rode antes: uv run python -m preditor {camada_anterior}"
            )
        return self.spark.read.parquet(str(arquivo))

    def _salvar(self, baseline: DataFrame, features: DataFrame) -> DataFrame:
        config.GOLD.mkdir(parents=True, exist_ok=True)
        baseline.write.mode("overwrite").parquet(str(config.ARQUIVO_BASELINE))
        features.write.mode("overwrite").parquet(str(config.ARQUIVO_FEATURES))
        # Relê do disco: as verificações usam o arquivo gravado, sem recalcular.
        return self.spark.read.parquet(str(config.ARQUIVO_FEATURES))

    @staticmethod
    def _relatorio(baseline: DataFrame) -> None:
        relatorio = RelatorioRegiao()
        limites = relatorio.limites(baseline)
        relatorio.salvar_csv(limites, config.ARQUIVO_LIMITES)
        limites.show(truncate=False)

    def _verificar_bronze(self, linhas_bigquery: int, colunas_bigquery: list[tuple[str, str]]) -> None:
        """Checagens do Bronze: o Parquet gravado tem as linhas e colunas do BigQuery."""
        gravado = Bronze(self.spark).ler_parquet()
        linhas_parquet = gravado.count()
        assert linhas_parquet == linhas_bigquery, (
            f"Bronze com {linhas_parquet} linhas, BigQuery tem {linhas_bigquery}"
        )
        # dtypes inclui o tipo: confere também que `pings` continua aninhado.
        assert gravado.dtypes == colunas_bigquery, "Colunas do Bronze diferem das do BigQuery"
        print(f"Bronze: {linhas_parquet} linhas = BigQuery | {len(gravado.columns)} colunas | {config.ARQUIVO_BRONZE}")

    def _verificar_silver(self) -> None:
        """Checagens do Silver, sobre o Parquet gravado: param o programa se algo estiver errado."""
        silver = self.spark.read.parquet(str(config.ARQUIVO_SILVER))

        # RTT nulo (medição sem resposta) é permitido; 0 ou negativo, não (RTT válido = rtt > 0).
        assert silver.filter(F.col("rtt") <= 0).count() == 0, "Silver com rtt <= 0"

        periodos = {linha.periodo for linha in silver.select("periodo").distinct().collect()}
        assert periodos <= {"A", "B"}, f"Silver com periodo inesperado: {periodos}"

        fluxos = silver.select("fluxo_id").distinct().count()
        assert fluxos == config.FLUXOS_SILVER, (
            f"Silver com {fluxos} fluxos distintos, esperado {config.FLUXOS_SILVER}"
        )
        print(f"Silver: {silver.count()} medições | {fluxos} fluxos | períodos {sorted(periodos)} | {config.ARQUIVO_SILVER}")

    @staticmethod
    def _verificar_gold(medicoes: DataFrame, baseline: DataFrame, features: DataFrame) -> None:
        """Checagens do Gold: param o programa se algo estiver errado."""
        corte = medicoes.filter(F.col("periodo") == "B").agg(F.min("t").cast("string")).first()[0]
        vazou_a = features.filter(F.col("t") < F.lit(corte).cast("timestamp")).count()
        assert vazou_a == 0, "Período A vazou para as features"

        total = baseline.count()
        insuficientes = baseline.filter("baseline_insuficiente").select("fluxo_id").collect()
        assert total == config.FLUXOS_BASELINE, (
            f"Baseline com {total} fluxos, esperado {config.FLUXOS_BASELINE}"
        )
        assert len(insuficientes) == config.FLUXOS_INSUFICIENTES, (
            f"Baseline com {len(insuficientes)} fluxos insuficientes, esperado {config.FLUXOS_INSUFICIENTES}"
        )
        # left_anti = fluxos que existem nas medições mas não têm linha no baseline.
        sem_periodo_a = (
            medicoes.select("fluxo_id").distinct().join(baseline, "fluxo_id", "left_anti").collect()
        )

        print(f"Fluxos: {total} | com baseline: {total - len(insuficientes)} | insuficientes: {len(insuficientes)}")
        for linha in insuficientes:
            print(f"  baseline_insuficiente: {linha.fluxo_id}")
        for linha in sem_periodo_a:
            print(f"  sem medições no Período A (fora do modelo): {linha.fluxo_id}")
        print(f"Corte A/B: {corte} | linhas de features (B): {features.count()}")


def main() -> None:
    analisador = argparse.ArgumentParser(prog="preditor", description="Pipeline do preditor de falhas.")
    analisador.add_argument(
        "camada",
        nargs="?",  # opcional: sem argumento roda o pipeline completo
        choices=["bronze", "silver", "gold"],
        help="camada a rodar isoladamente (sem argumento: pipeline completo)",
    )
    camada = analisador.parse_args().camada

    # O conector do BigQuery só é necessário quando a execução inclui o Bronze.
    spark = build_spark(com_bigquery=camada in (None, "bronze"))
    try:
        pipeline = Pipeline(spark)
        # Sem argumento, roda as camadas em sequência; cada uma lê a anterior do disco.
        if camada in (None, "bronze"):
            pipeline.executar_bronze()
        if camada in (None, "silver"):
            pipeline.executar_silver()
        if camada in (None, "gold"):
            pipeline.executar_gold()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
