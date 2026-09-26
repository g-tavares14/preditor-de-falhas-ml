from pyspark.sql import SparkSession


def build_spark() -> SparkSession:
    """Cria a sessão Spark local já com o conector do BigQuery.

    - `local[*]`: roda na própria máquina, usando todos os núcleos.
    - `spark.jars.packages`: baixa o conector BigQuery na primeira execução.
    - Autenticação: usa o login do gcloud (`gcloud auth application-default login`).
    - Fuso UTC: as medições do RIPE Atlas são em UTC; fixar evita que o
      horário local do Mac desloque o corte entre os períodos.
    """
    return (
        SparkSession.builder
        .master("local[*]")
        .appName("preditor-degradacao")
        .config("spark.jars.packages", "com.google.cloud.spark:spark-3.5-bigquery:0.45.0")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
