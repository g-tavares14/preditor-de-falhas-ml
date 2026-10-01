"""Camada Bronze: lê a tabela inteira do BigQuery e grava como está.

Sem filtro e sem cálculo: mesmas colunas, e `pings` continua aninhado (lista de
structs). É a única etapa que precisa de rede e de credenciais do gcloud; as
camadas seguintes leem o Parquet gravado aqui (SPEC-medalhao.md).
"""

from pyspark.sql import DataFrame, SparkSession

from preditor import config


class Bronze:
    def __init__(self, spark: SparkSession):
        self.spark = spark

    def ler_bigquery(self) -> DataFrame:
        # O Spark é "preguiçoso": isto só descreve a leitura. Os dados só são
        # baixados quando algo precisar do resultado (um write, count, show...).
        return (
            self.spark.read.format("bigquery")
            .option("parentProject", config.PROJECT)
            .option("location", config.LOCATION)
            .load(config.TABLE)
        )

    def ingerir(self) -> tuple[int, list[tuple[str, str]]]:
        """Grava a tabela do BigQuery em `config.ARQUIVO_BRONZE`.

        Devolve (nº de linhas, colunas com tipo) como vieram do BigQuery, para o
        `__main__` conferir contra o Parquet gravado.
        """
        bruto = self.ler_bigquery()
        # count() antes do write: o conector responde sem baixar os dados.
        linhas_bigquery = bruto.count()
        colunas_bigquery = bruto.dtypes  # lista de (nome, tipo)

        config.BRONZE.mkdir(parents=True, exist_ok=True)
        # mode("overwrite"): rodar de novo substitui o Bronze anterior.
        bruto.write.mode("overwrite").parquet(str(config.ARQUIVO_BRONZE))
        return linhas_bigquery, colunas_bigquery

    def ler_parquet(self) -> DataFrame:
        """Lê o Bronze do disco (é o que as camadas seguintes usam)."""
        return self.spark.read.parquet(str(config.ARQUIVO_BRONZE))
