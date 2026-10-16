from pyspark.sql import SparkSession


def build_spark(com_bigquery: bool) -> SparkSession:
    """Cria a sessão Spark local; o conector do BigQuery só entra se `com_bigquery`.

    - `local[*]`: roda na própria máquina, usando todos os núcleos.
    - `spark.jars.packages`: baixa o conector BigQuery (Ivy) na primeira execução. Só é
      declarado quando a execução vai ler o BigQuery (camada `bronze` ou pipeline
      completo); `silver` e `gold` não o declaram, para rodarem offline mesmo numa
      máquina sem o cache do Ivy.
    - Autenticação: usa o login do gcloud (`gcloud auth application-default login`).
    - Fuso UTC: as medições do RIPE Atlas são em UTC; fixar evita que o
      horário local do Mac desloque o corte entre os períodos.
    """
    construtor = (
        SparkSession.builder
        .master("local[*]")
        .appName("preditor-degradacao")
        .config("spark.sql.session.timeZone", "UTC")
    )
    if com_bigquery:
        construtor = construtor.config(
            "spark.jars.packages", "com.google.cloud.spark:spark-3.5-bigquery:0.45.0"
        )
    return construtor.getOrCreate()
