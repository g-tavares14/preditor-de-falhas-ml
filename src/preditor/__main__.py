"""Ponto de entrada: `uv run python -m preditor`.

Fluxo: BigQuery → medições → baseline (Período A) → features (Período B) → arquivos.
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from preditor import config
from preditor.baseline import Baseline
from preditor.features import Features
from preditor.medicao import Medicoes
from preditor.relatorio_regiao import RelatorioRegiao
from preditor.spark import build_spark


class Pipeline:
    def __init__(self, spark: SparkSession):
        self.spark = spark

    def executar(self) -> None:
        # .cache() guarda o resultado em memória: medições e baseline são
        # usados várias vezes abaixo e não queremos reler o BigQuery a cada uso.
        medicoes = Medicoes(self.spark).carregar().cache()
        baseline = Baseline().calcular(medicoes).cache()
        features = Features().construir(medicoes, baseline)

        features = self._salvar(baseline, features)
        self._relatorio(baseline)
        self._verificar(medicoes, baseline, features)

    def _salvar(self, baseline: DataFrame, features: DataFrame) -> DataFrame:
        config.SAIDA.mkdir(parents=True, exist_ok=True)
        baseline.write.mode("overwrite").parquet(str(config.SAIDA / "baseline_por_fluxo.parquet"))
        caminho = str(config.SAIDA / "features_B.parquet")
        features.write.mode("overwrite").parquet(caminho)
        # Relê do disco: as verificações usam o arquivo gravado, sem recalcular.
        return self.spark.read.parquet(caminho)

    @staticmethod
    def _relatorio(baseline: DataFrame) -> None:
        relatorio = RelatorioRegiao()
        limites = relatorio.limites(baseline)
        relatorio.salvar_csv(limites, config.SAIDA / "limites_por_regiao.csv")
        limites.show(truncate=False)

    @staticmethod
    def _verificar(medicoes: DataFrame, baseline: DataFrame, features: DataFrame) -> None:
        """Checagens de sanidade: param o programa se algo estiver errado."""
        corte = medicoes.filter(F.col("periodo") == "B").agg(F.min("t").cast("string")).first()[0]
        vazou_a = features.filter(F.col("t") < F.lit(corte).cast("timestamp")).count()
        assert vazou_a == 0, "Período A vazou para as features"
        assert medicoes.filter(F.col("rtt") <= 0).count() == 0, "rtt <= 0 entrou como válido"

        total = baseline.count()
        insuficientes = baseline.filter("baseline_insuficiente").select("fluxo_id").collect()
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
    spark = build_spark()
    try:
        Pipeline(spark).executar()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
