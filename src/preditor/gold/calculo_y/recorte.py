"""Camada Gold, cálculo do Y: o recorte temporal do dataset rotulado em treino / validação / teste.

Dois instantes de corte, iguais para todos os fluxos (Tarefa 2, seção 5, e RFC §9). Não há sorteio de
linhas: cada medição cai no bloco do seu instante, então o teste fica sempre depois do treino.
"""

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from preditor import config

# Formato fixo (data, hora e milissegundos) para mostrar e gravar instantes. Com largura fixa, comparar
# dois textos é o mesmo que comparar os dois instantes. Os `t` são segundos inteiros, e 50 % e 70 % de um
# número inteiro de segundos têm no máximo uma casa decimal: os milissegundos mostram o corte exato.
FORMATO_INSTANTE = "yyyy-MM-dd HH:mm:ss.SSS"
BLOCOS = ("treino", "validacao", "teste")  # em ordem de tempo


class Recorte:
    def recortar(self, rotulado: DataFrame) -> DataFrame:
        """Devolve o dataset rotulado com a coluna `bloco` (treino / validacao / teste) a mais."""
        # crossJoin cola uma linha só (os dois instantes de corte) em todas as linhas, como
        # `Medicoes._marcar_periodo` faz com o início do Período A. Os cortes são calculados dentro do
        # Spark, sem passar timestamps pelo Python, para não sofrer conversão de fuso horário.
        bloco = (
            F.when(F.col("t") < F.col("corte_1"), "treino")
            .when(F.col("t") < F.col("corte_2"), "validacao")
            .otherwise("teste")
        )
        return (
            rotulado.crossJoin(self.cortes(rotulado))
            .withColumn("bloco", bloco)
            .drop("corte_1", "corte_2")
        )

    @staticmethod
    def cortes(rotulado: DataFrame) -> DataFrame:
        """Uma linha com `corte_1` e `corte_2` (timestamps), a 50 % e 70 % entre o menor e o maior `t`."""
        # unix_micros dá o instante como um número inteiro (microssegundos desde 1970): a conta
        # t_min + fração × (t_max − t_min) vira aritmética comum, sem arredondar para segundos.
        extremos = rotulado.agg(
            F.unix_micros(F.min("t")).alias("t_min"),
            F.unix_micros(F.max("t")).alias("t_max"),
        )

        def instante(fracao: float) -> Column:
            microssegundos = F.col("t_min") + ((F.col("t_max") - F.col("t_min")) * fracao).cast("long")
            return F.timestamp_micros(microssegundos)  # volta a ser timestamp

        return extremos.select(
            instante(config.FRACAO_TREINO).alias("corte_1"),
            instante(config.FRACAO_TREINO + config.FRACAO_VALIDACAO).alias("corte_2"),
        )

    def contagem(self, rotulado: DataFrame) -> DataFrame:
        """Uma linha por bloco (em ordem de tempo): início, fim, N por classe e os dois instantes de corte.

        Os instantes saem como texto de largura fixa (`FORMATO_INSTANTE`), prontos para imprimir e gravar.
        """

        def n_da_classe(classe: str) -> Column:
            # (condição).cast("int") vale 1 ou 0: somar conta as linhas daquela classe.
            return F.sum((F.col("status_atual") == classe).cast("int")).alias(f"n_{classe.lower()}")

        por_bloco = rotulado.groupBy("bloco").agg(
            F.min("t").alias("inicio"),
            F.max("t").alias("fim"),
            F.count("*").alias("n"),
            n_da_classe("OK"),
            n_da_classe("RISCO"),
            n_da_classe("FALHA"),
        )
        ordem = F.when(F.col("bloco") == "treino", 1).when(F.col("bloco") == "validacao", 2).otherwise(3)
        return (
            por_bloco.crossJoin(self.cortes(rotulado))
            .orderBy(ordem)
            .select(
                "bloco",
                F.date_format("inicio", FORMATO_INSTANTE).alias("inicio"),
                F.date_format("fim", FORMATO_INSTANTE).alias("fim"),
                F.date_format("corte_1", FORMATO_INSTANTE).alias("corte_1"),
                F.date_format("corte_2", FORMATO_INSTANTE).alias("corte_2"),
                "n",
                "n_ok",
                "n_risco",
                "n_falha",
            )
        )
