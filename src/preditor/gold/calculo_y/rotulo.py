"""Camada Gold, cálculo do Y: o rótulo OK / RISCO / FALHA de cada medição do Período B.

O Y não recalcula nenhuma métrica: lê as colunas que o X já tem (`perda_pct`,
`n5_timeout`, `z_robusto`, `aumento_pct`, `n5_aumento80`, `moderado`, `n5_moderado`) e
aplica a tabela de rótulo da RFC §8.4, com o piso da linha 3 (SPEC-piso-regra3.md).
Região, país, IP e `fluxo_id` não participam da regra.
"""

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

from preditor import config


class Rotulo:
    def rotular(self, features: DataFrame) -> DataFrame:
        """Devolve as features com três colunas a mais: `regra` (1 a 6), `status_atual` e `status_futuro`."""
        # A regra vem primeiro e a classe é derivada dela: assim, as duas nunca divergem
        # e `regra` serve para auditar qual linha da tabela da RFC decidiu cada medição.
        # O `status_futuro` vem por último porque copia o `status_atual` de outra linha.
        return (
            features.withColumn("regra", self._regra())
            .withColumn("status_atual", self._status_da_regra())
            .withColumn("status_futuro", self._status_futuro())
        )

    @staticmethod
    def _regra() -> Column:
        """Número da primeira linha verdadeira da tabela da RFC §8.4 (1 a 6)."""
        # when() encadeado = "se... senão se...": o Spark testa na ordem e para na primeira
        # condição verdadeira, igual à tabela da RFC. Comparação com nulo dá nulo, e o when()
        # trata nulo como falso: sem RTT, `z_robusto` é nulo e a linha 3 simplesmente não dispara
        # (essas medições já caem na linha 1, porque perderam todos os pacotes).
        # Linha 3 com piso (decisão de 09/10/2026, SPEC-piso-regra3.md): z extremo só é FALHA quando o RTT também
        # subiu o piso sobre a mediana. Piso None = a regra da RFC ao pé da letra (só o z).
        falha_por_z = F.col("z_robusto") >= config.Z_FALHA
        if config.PISO_AUMENTO_FALHA_PCT is not None:
            falha_por_z = falha_por_z & (F.col("aumento_pct") >= config.PISO_AUMENTO_FALHA_PCT)
        return (
            F.when(F.col("perda_pct") >= config.PERDA_FALHA_PCT, 1)
            .when(F.col("n5_timeout") >= config.N5_TIMEOUT_FALHA, 2)
            .when(falha_por_z, 3)
            .when(F.col("n5_aumento80") >= config.N5_AUMENTO80_FALHA, 4)
            .when((F.col("moderado") == 1) & (F.col("n5_moderado") >= config.N5_RISCO), 5)
            .otherwise(6)
        )

    @staticmethod
    def _status_da_regra() -> Column:
        """Classe de cada regra: 1 a 4 = FALHA, 5 = RISCO, 6 = OK (RFC §8.4)."""
        return (
            F.when(F.col("regra") <= 4, "FALHA")
            .when(F.col("regra") == 5, "RISCO")
            .otherwise("OK")
        )

    @staticmethod
    def _status_futuro() -> Column:
        """`status_atual` da 3ª medição seguinte do mesmo fluxo (12 min depois, RFC §3), ou nulo."""
        # Janela = "o grupo de linhas que a função enxerga": uma por fluxo (partitionBy) e, dentro
        # dela, em ordem de tempo (orderBy). Sem duplicatas no Silver, a ordem por `t` é única.
        janela = Window.partitionBy("fluxo_id").orderBy("t")
        # lead(coluna, n) devolve o valor da coluna n linhas ADIANTE na janela (nulo se a janela
        # acaba antes). Aqui n = 3: a 3ª medição seguinte do mesmo fluxo, nunca de outro.
        status_depois = F.lead("status_atual", config.PASSOS_FUTURO).over(janela)
        # cast("long") em timestamp dá segundos desde 1970: a diferença não depende de fuso.
        t_depois = F.lead(F.col("t").cast("long"), config.PASSOS_FUTURO).over(janela)
        segundos = t_depois - F.col("t").cast("long")
        # when() sem otherwise() dá nulo quando a condição é falsa ou nula: sem 3ª medição
        # (`segundos` nulo) ou com lacuna (fora de 600 a 840 s), o futuro não é "12 min depois".
        return F.when(segundos.between(config.FUTURO_MIN_S, config.FUTURO_MAX_S), status_depois)
