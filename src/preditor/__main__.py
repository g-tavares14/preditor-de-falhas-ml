"""Ponto de entrada: `uv run python -m preditor [camada]`.

Sem argumento: Bronze (BigQuery → Parquet) → Silver (medições) → Gold (baseline do
Período A, features e rótulo do Período B). Com `bronze`: só a ingestão do BigQuery.
Com `silver`: só a normalização, lendo o Bronze do disco (sem rede).
Com `gold`: só baseline, features e rótulo, lendo o Silver do disco (sem rede).
Cada camada lê a anterior do disco, nunca da memória.
Com `arvore`: a árvore de decisão, lendo o Gold do disco e gravando em `data/modelo/` (sem rede, sem Spark e
sem Java); não entra na execução sem argumento. O código dela fica em `preditor/modelo/`.
"""

import argparse
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from preditor import config
from preditor.bronze.ingestao import Bronze
from preditor.gold.calculo_x.baseline import Baseline
from preditor.gold.calculo_x.features import Features
from preditor.gold.calculo_x.relatorio_regiao import RelatorioRegiao
from preditor.gold.calculo_y.recorte import BLOCOS, Recorte
from preditor.gold.calculo_y.rotulo import Rotulo
from preditor.modelo.execucao import ExecucaoArvore
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
        # O Silver tem uma linha por linha do Bronze, menos as duplicatas removidas.
        self._verificar_silver(linhas_bronze=bronze.count())

    def executar_gold(self) -> None:
        """Lê o Silver do disco, calcula baseline, features e rótulo, grava o Gold, conferindo o resultado."""
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

        # O rótulo parte das features relidas do disco (as mesmas que o X gravou) e
        # é gravado à parte: `features_B.parquet` continua sem as colunas do Y.
        com_rotulo = Rotulo().rotular(features)
        # O recorte vem depois do rótulo: `bloco` só olha o tempo de cada medição.
        com_bloco = Recorte().recortar(com_rotulo)
        rotulado = self._salvar_rotulo(com_bloco)
        # A contagem por bloco só é gravada depois que todas as checagens passam.
        contagem = self._verificar_rotulo(features, rotulado)
        self._salvar_contagem(contagem)
        self._imprimir_exemplos(rotulado)

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

    def _salvar_rotulo(self, rotulado: DataFrame) -> DataFrame:
        rotulado.write.mode("overwrite").parquet(str(config.ARQUIVO_ROTULADO))
        # Relê do disco: as checagens valem para o arquivo que o modelo vai ler.
        return self.spark.read.parquet(str(config.ARQUIVO_ROTULADO))

    @staticmethod
    def _salvar_contagem(contagem: DataFrame) -> None:
        """Grava `contagem_classes.csv` (bloco × classe e instantes de corte), só para leitura humana."""
        RelatorioRegiao.salvar_csv(contagem, config.ARQUIVO_CONTAGEM)
        print(f"Contagem por bloco e classe gravada em {config.ARQUIVO_CONTAGEM}")

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

    def _verificar_silver(self, linhas_bronze: int) -> None:
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
        # Uma medição = um (fluxo_id, t). Se algum par aparece mais de uma vez, a remoção
        # de duplicatas em `Medicoes.transformar` falhou (ou há linhas diferentes no mesmo instante).
        repetidos = silver.groupBy("fluxo_id", "t").count().filter("count > 1").count()
        assert repetidos == 0, f"Silver com {repetidos} pares (fluxo_id, t) repetidos"

        linhas_silver = silver.count()
        print(f"Silver: {linhas_silver} medições | {fluxos} fluxos | períodos {sorted(periodos)} | {config.ARQUIVO_SILVER}")
        print(f"Duplicatas removidas no Silver: {linhas_bronze - linhas_silver} (Bronze {linhas_bronze} linhas)")

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

    @staticmethod
    def _verificar_rotulo(features: DataFrame, rotulado: DataFrame) -> DataFrame:
        """Checagens do rótulo, sobre o Parquet gravado: param o programa se algo estiver errado.

        Devolve a contagem por bloco (para `_salvar_contagem`), sem gravar nada.
        """
        linhas = Pipeline._verificar_status_atual(features, rotulado)
        # A saída lê na ordem do dataset: rótulo, `status_atual`, `status_futuro`, recorte.
        print(f"Rótulo: {linhas} linhas = features | {config.ARQUIVO_ROTULADO}")
        Pipeline._imprimir_distribuicao(rotulado, linhas)
        Pipeline._verificar_futuro(rotulado)
        return Pipeline._verificar_recorte(rotulado)

    @staticmethod
    def _verificar_status_atual(features: DataFrame, rotulado: DataFrame) -> int:
        """Checagens de colunas, `regra` e `status_atual`. Devolve o número de linhas do dataset rotulado."""
        # Nenhuma medição some nem aparece: o rótulo só acrescenta colunas.
        linhas = rotulado.count()
        linhas_features = features.count()
        assert linhas == linhas_features, (
            f"Dataset rotulado com {linhas} linhas, features tem {linhas_features}"
        )
        # Conjunto exato de colunas: garante também que nenhuma coluna auxiliar (posição,
        # diferença de tempo) do `status_futuro` ficou no arquivo.
        assert rotulado.columns == features.columns + ["regra", "status_atual", "status_futuro", "bloco"], (
            "Colunas do dataset rotulado diferem das features + regra + status_atual + status_futuro + bloco"
        )

        # `status_atual` completo: nunca nulo e só com as três classes.
        classes = {linha.status_atual for linha in rotulado.select("status_atual").distinct().collect()}
        assert classes <= {"OK", "RISCO", "FALHA"}, f"status_atual com valor inesperado (ou nulo): {classes}"

        # Coerência regra ↔ classe (RFC §8.4: 1 a 4 = FALHA, 5 = RISCO, 6 = OK). Um filtro com
        # `regra` nula daria nulo (e nulo não entra no filtro), então conferimos à parte
        # que `regra` nunca é nula nem fica fora de 1 a 6.
        regra_invalida = rotulado.filter(~F.col("regra").between(1, 6) | F.col("regra").isNull()).count()
        assert regra_invalida == 0, f"{regra_invalida} linhas com regra fora de 1 a 6 (ou nula)"
        incoerentes = rotulado.filter(
            ((F.col("regra") <= 4) & (F.col("status_atual") != "FALHA"))
            | ((F.col("regra") == 5) & (F.col("status_atual") != "RISCO"))
            | ((F.col("regra") == 6) & (F.col("status_atual") != "OK"))
        ).count()
        assert incoerentes == 0, f"{incoerentes} linhas com regra e status_atual incoerentes"

        # Precedência: FALHA ganha de tudo (RFC §8.4). Perda >= 10 % é sempre FALHA, e uma
        # linha OK nunca tem z extremo (z nulo, sem RTT, não entra: já é FALHA pela perda).
        perda_sem_falha = rotulado.filter(
            (F.col("perda_pct") >= config.PERDA_FALHA_PCT) & (F.col("status_atual") != "FALHA")
        ).count()
        assert perda_sem_falha == 0, f"{perda_sem_falha} linhas com perda >= {config.PERDA_FALHA_PCT}% que não são FALHA"
        ok_com_z_extremo = rotulado.filter(
            (F.col("status_atual") == "OK") & (F.col("z_robusto") >= config.Z_FALHA)
        ).count()
        assert ok_com_z_extremo == 0, f"{ok_com_z_extremo} linhas OK com z_robusto >= {config.Z_FALHA}"

        return linhas

    @staticmethod
    def _verificar_futuro(rotulado: DataFrame) -> None:
        """Confere `status_futuro` por um caminho independente do `lead` usado em `Rotulo`."""
        # `status_futuro` é nulo ou uma das três classes.
        valores = {linha.status_futuro for linha in rotulado.select("status_futuro").distinct().collect()}
        assert valores <= {"OK", "RISCO", "FALHA", None}, f"status_futuro com valor inesperado: {valores}"

        # Caminho independente: numera as medições de cada fluxo por `t` (row_number) e liga cada
        # linha à de posição + PASSOS_FUTURO com um join comum, sem usar `lead`.
        numeradas = rotulado.select("fluxo_id", "t", "status_atual", "status_futuro").withColumn(
            "posicao", F.row_number().over(Window.partitionBy("fluxo_id").orderBy("t"))
        )
        # Cada linha "aparece" com a posição de quem está PASSOS_FUTURO medições antes dela:
        # no join, a medição de posição p recebe os dados da medição de posição p + 3.
        destino = numeradas.select(
            "fluxo_id",
            (F.col("posicao") - config.PASSOS_FUTURO).alias("posicao"),
            F.col("t").cast("long").alias("t_destino"),
            F.col("status_atual").alias("status_destino"),
        )
        # left join: linhas sem 3ª medição à frente ficam com `t_destino` nulo.
        ligadas = numeradas.join(destino, ["fluxo_id", "posicao"], "left").withColumn(
            "diferenca_s", F.col("t_destino") - F.col("t").cast("long")
        )

        # coalesce(..., False): comparação com nulo dá nulo e o filter() descartaria a linha em
        # silêncio; aqui "sem 3ª medição" precisa contar como "fora do intervalo".
        no_intervalo = F.coalesce(
            F.col("diferenca_s").between(config.FUTURO_MIN_S, config.FUTURO_MAX_S), F.lit(False)
        )
        mesmo_status = F.coalesce(F.col("status_destino") == F.col("status_futuro"), F.lit(False))
        # (1) status_futuro não nulo => a 3ª medição existe, está em 600 a 840 s e tem esse status.
        futuro_errado = ligadas.filter(F.col("status_futuro").isNotNull() & ~(no_intervalo & mesmo_status)).count()
        assert futuro_errado == 0, f"{futuro_errado} linhas com status_futuro que não bate com a 3ª medição à frente"
        # (2) sentido inverso: 3ª medição existe e está no intervalo => status_futuro não nulo.
        futuro_faltando = ligadas.filter(F.col("status_futuro").isNull() & no_intervalo).count()
        assert futuro_faltando == 0, f"{futuro_faltando} linhas com status_futuro nulo, mas com 3ª medição válida"

        # Por que o futuro é nulo: a série acabou (sem 3ª medição) ou houve lacuna (fora de 600 a 840 s).
        nulos = ligadas.filter(F.col("status_futuro").isNull())
        fim_da_serie = nulos.filter(F.col("t_destino").isNull()).count()
        curta = nulos.filter(F.col("diferenca_s") < config.FUTURO_MIN_S).count()
        longa = nulos.filter(F.col("diferenca_s") > config.FUTURO_MAX_S).count()
        total_nulos = fim_da_serie + curta + longa
        print(f"status_futuro nulo: {total_nulos} linhas")
        print(f"  fim da série (sem {config.PASSOS_FUTURO} medições à frente): {fim_da_serie}")
        print(
            f"  lacuna ({config.PASSOS_FUTURO}ª medição fora de {config.FUTURO_MIN_S} a {config.FUTURO_MAX_S} s): "
            f"{curta + longa} ({curta} abaixo de {config.FUTURO_MIN_S} s, {longa} acima de {config.FUTURO_MAX_S} s)"
        )
        assert total_nulos == nulos.count(), "Motivos do status_futuro nulo não somam o total de nulos"

        com_futuro = rotulado.filter(F.col("status_futuro").isNotNull())
        n_futuro = com_futuro.count()
        # As divisões abaixo usam n_futuro: sem nenhuma linha com futuro, daria divisão por zero.
        assert n_futuro > 0, "Nenhuma linha com status_futuro: confira PASSOS_FUTURO, FUTURO_MIN_S e FUTURO_MAX_S"
        por_classe = {linha.status_futuro: linha["count"] for linha in com_futuro.groupBy("status_futuro").count().collect()}
        print(f"status_futuro: {n_futuro} linhas com valor")
        for classe in ("OK", "RISCO", "FALHA"):
            n = por_classe.get(classe, 0)
            print(f"  {classe:<5}: {n:>7} ({n / n_futuro * 100:.1f} %)")
        mudaram = com_futuro.filter(F.col("status_futuro") != F.col("status_atual")).count()
        print(f"  status_futuro diferente de status_atual: {mudaram} ({mudaram / n_futuro * 100:.1f} %)")

    @staticmethod
    def _verificar_recorte(rotulado: DataFrame) -> DataFrame:
        """Checagens de `bloco` e impressão dos cortes e do N por classe. Devolve a contagem por bloco."""
        # `bloco` completo: nunca nulo e só com os três valores. Um valor nulo apareceria no
        # distinct() como None, que não está em BLOCOS.
        blocos = {linha.bloco for linha in rotulado.select("bloco").distinct().collect()}
        assert blocos == set(BLOCOS), f"bloco com valores diferentes de {BLOCOS} (ou nulo): {blocos}"

        # Uma linha por bloco, em ordem de tempo. Início, fim e cortes são texto de largura fixa
        # (ver `FORMATO_INSTANTE`): comparar os textos é comparar os instantes, sem passar por
        # timestamps do Python (conversão de fuso).
        contagem = Recorte().contagem(rotulado)
        por_bloco = {linha.bloco: linha for linha in contagem.collect()}
        treino, validacao, teste = (por_bloco[b] for b in BLOCOS)

        # O tempo manda: tudo que é treino acontece antes de tudo que é validação, e esta antes do
        # teste. Cada corte separa os dois blocos: o fim de um bloco é anterior ao corte (`t < corte`
        # em `Recorte.recortar`) e o início do seguinte é no corte ou depois dele.
        assert treino.fim < treino.corte_1 <= validacao.inicio, (
            f"Treino termina em {treino.fim}, corte 1 em {treino.corte_1}, validação começa em {validacao.inicio}: "
            "esperado fim do treino < corte 1 <= início da validação"
        )
        assert validacao.fim < treino.corte_2 <= teste.inicio, (
            f"Validação termina em {validacao.fim}, corte 2 em {treino.corte_2}, teste começa em {teste.inicio}: "
            "esperado fim da validação < corte 2 <= início do teste"
        )

        # Cada bloco precisa ter as três classes, senão não dá para treinar nem avaliar o modelo.
        for linha in (treino, validacao, teste):
            for classe, n in (("OK", linha.n_ok), ("RISCO", linha.n_risco), ("FALHA", linha.n_falha)):
                assert n > 0, (
                    f"Bloco {linha.bloco} sem nenhuma linha {classe}: ajuste FRACAO_TREINO e FRACAO_VALIDACAO em config.py"
                )

        fracao_teste = 1 - config.FRACAO_TREINO - config.FRACAO_VALIDACAO
        print(
            f"Recorte ({config.FRACAO_TREINO:.0%} / {config.FRACAO_VALIDACAO:.0%} / {fracao_teste:.0%} do tempo, "
            "sem folga entre blocos)"
        )
        print(f"  corte 1 (treino | validação): {treino.corte_1}")
        print(f"  corte 2 (validação | teste):  {treino.corte_2}")
        print(f"  {'bloco':<10}{'N':>8}{'OK':>8}{'RISCO':>8}{'FALHA':>8}")
        for linha in (treino, validacao, teste):
            print(f"  {linha.bloco:<10}{linha.n:>8}{linha.n_ok:>8}{linha.n_risco:>8}{linha.n_falha:>8}")
        return contagem

    @staticmethod
    def _imprimir_distribuicao(rotulado: DataFrame, linhas: int) -> None:
        """Mostra quantas medições há por classe (com %) e por regra."""
        por_classe = {
            linha.status_atual: linha["count"] for linha in rotulado.groupBy("status_atual").count().collect()
        }
        for classe in ("OK", "RISCO", "FALHA"):
            n = por_classe.get(classe, 0)
            print(f"  {classe:<5}: {n:>7} ({n / linhas * 100:.1f} %)")
        print("  Por regra (RFC §8.4):")
        for linha in rotulado.groupBy("regra", "status_atual").count().orderBy("regra").collect():
            print(f"    regra {linha.regra} ({linha.status_atual}): {linha['count']}")

    @staticmethod
    def _imprimir_exemplos(rotulado: DataFrame) -> None:
        """Imprime três linhas reais do dataset para o diário da Tarefa 2 (seção 4): OK, RISCO e FALHA.

        A escolha é determinística: cada exemplo é o primeiro de uma lista ORDENADA, e o último critério
        de ordem (`fluxo_id`, `t`) identifica uma única medição. Rodar de novo imprime as mesmas linhas.
        `rota` e `fluxo_id` só ajudam o leitor a achar a linha: nenhuma regra os usa.
        """
        # t como texto: collect() converteria o timestamp para o fuso do Python.
        colunas = [
            "fluxo_id", "rota", F.col("t").cast("string").alias("t"), "rtt", "z_robusto", "aumento_pct",
            "jitter_relativo", "perda_pct", "n5_timeout", "n5_aumento80", "n5_moderado", "regra", "status_atual",
        ]
        meio_do_risco = (config.Z_RISCO + config.Z_FALHA) / 2  # centro da faixa moderada de z (2,75)

        exemplos = [
            (
                "OK de caminho longo",
                f"entre as linhas OK com |z_robusto| <= {config.EXEMPLO_OK_Z_MAX} e n5_moderado = 0, a de maior rtt",
                # n5_moderado = 0: nenhuma das últimas 5 medições teve desvio, o OK mais "limpo" para o diário.
                rotulado.filter(
                    (F.col("status_atual") == "OK")
                    & (F.abs("z_robusto") <= config.EXEMPLO_OK_Z_MAX)
                    & (F.col("n5_moderado") == 0)
                ).orderBy(F.desc("rtt"), "fluxo_id", "t"),
            ),
            (
                "RISCO (regra 5)",
                f"entre as linhas da regra 5 com z_robusto na faixa moderada ({config.Z_RISCO} a {config.Z_FALHA}) "
                f"e n5_moderado = {config.JANELA}, a de z mais próximo de {meio_do_risco}",
                rotulado.filter(
                    (F.col("regra") == 5)
                    & F.col("z_robusto").between(config.Z_RISCO, config.Z_FALHA)
                    & (F.col("n5_moderado") == config.JANELA)
                ).orderBy(F.abs(F.col("z_robusto") - meio_do_risco), "fluxo_id", "t"),
            ),
            (
                "FALHA de caminho curto (regra 3)",
                f"entre as linhas da regra 3 com z_robusto >= {config.EXEMPLO_FALHA_Z_MIN}, a de menor rtt",
                # z com folga sobre o limiar (3,5): refazer a conta com valores arredondados não muda a classe.
                rotulado.filter((F.col("regra") == 3) & (F.col("z_robusto") >= config.EXEMPLO_FALHA_Z_MIN))
                .orderBy("rtt", "fluxo_id", "t"),
            ),
        ]

        print("Exemplos reais para o diário da Tarefa 2 (seção 4):")
        for titulo, criterio, candidatas in exemplos:
            linhas = candidatas.select(*colunas).limit(1).collect()
            assert linhas, f"Nenhuma linha encontrada para o exemplo '{titulo}'"
            print(f"  {titulo}: {criterio}")
            for nome, valor in linhas[0].asDict().items():
                texto = "nulo" if valor is None else f"{valor:.4f}" if isinstance(valor, float) else valor
                print(f"    {nome:<16}{texto}")


def main() -> None:
    analisador = argparse.ArgumentParser(prog="preditor", description="Pipeline do preditor de falhas.")
    analisador.add_argument(
        "camada",
        nargs="?",  # opcional: sem argumento roda o pipeline completo
        choices=["bronze", "silver", "gold", "arvore"],
        help="camada a rodar isoladamente, ou `arvore` (sem argumento: pipeline completo)",
    )
    camada = analisador.parse_args().camada

    # A árvore lê o Gold com pandas: desvia antes de `build_spark`, que exige Java.
    # Por isso `arvore` também não entra na execução sem argumento.
    if camada == "arvore":
        ExecucaoArvore().executar()
        return

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
