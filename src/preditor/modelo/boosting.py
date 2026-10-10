"""XGBoost da comparação de modelos: busca na grade, escolha pela validação (SPEC-comparacao-modelos.md).

Igual à Random Forest (`floresta.py`) no X, no peso de classe, na semente, no treino SÓ com o bloco de treino e na regra
de escolha. Diferenças: o XGBoost trabalha com números, então OK, RISCO e FALHA viram 0, 1 e 2 só dentro deste módulo
(a previsão volta como texto); e não há parada antecipada (`early_stopping`), que olharia a validação para treinar.
Valores ausentes (`NaN`) entram como estão: o XGBoost escolhe para que lado vão em cada divisão (RFC §8.3).
"""

import itertools
import time

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from preditor import config
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.comparacao import escolher_por_regra
from preditor.modelo.dados import DadosModelo

# Código de cada classe dentro do XGBoost: a ordem de `config.CLASSES` (OK=0, RISCO=1, FALHA=2). Só este módulo usa
# os números; `prever` devolve o texto de volta.
CODIGO = {classe: codigo for codigo, classe in enumerate(config.CLASSES)}
CLASSE = list(config.CLASSES)  # o inverso de CODIGO: código → classe

# As colunas que identificam uma combinação da grade (cada uma aparece uma vez na busca).
COMBINACAO = ["n_estimators", "learning_rate", "max_depth"]
# A ordem de simplicidade do XGBoost, do mais simples para o mais complexo: menos rodadas; depois, mais rasa; depois,
# taxa de aprendizado maior (passos maiores, menos rodadas para chegar lá). Cada combinação aparece uma vez.
ORDEM_SIMPLICIDADE = [("n_estimators", True), ("max_depth", True), ("learning_rate", False)]


class Boosting:
    """O XGBoost da comparação: `buscar` treina a grade, mede cada modelo e guarda o escolhido."""

    def __init__(self) -> None:
        self.modelo: XGBClassifier | None = None  # o modelo escolhido, treinado só no treino
        self.busca = pd.DataFrame()  # uma linha por modelo, na ordem da grade
        # Segundos de treino de cada linha de `busca`. Ficam FORA da busca gravada: o tempo muda a cada execução
        # e o `comparar` precisa gravar arquivos idênticos quando roda duas vezes.
        self.tempos = pd.Series(dtype="float64")
        self.posicao_escolhida = -1  # índice do escolhido em `busca`

    def buscar(self, dados: DadosModelo) -> "Boosting":
        """Treina os modelos da grade no treino, mede cada um na validação e guarda o escolhido pela regra."""
        treino, validacao = config.BLOCO_TREINO, config.BLOCO_VALIDACAO
        linhas = []
        tempos = []
        modelos = []  # na mesma ordem de `linhas`

        grade = itertools.product(
            config.GRADE_ARVORES_BOOSTING, config.GRADE_TAXA_APRENDIZADO_BOOSTING, config.GRADE_PROFUNDIDADE_BOOSTING
        )
        for n_arvores, taxa, profundidade in grade:
            # Só o `fit` entra na conta do tempo: a medição de F1 logo abaixo não é treino.
            inicio = time.perf_counter()
            modelo = self._ajustar(dados, n_arvores, taxa, profundidade)
            tempos.append(time.perf_counter() - inicio)
            modelos.append(modelo)

            # Como na árvore ajustada e na floresta: o F1 de treino só mostra o quanto o modelo decora o treino; a
            # escolha usa a validação.
            f1_treino = Avaliacao.medir(
                dados.y[treino], self.prever_em(modelo, dados.x_ajustado(treino)), bloco=treino
            ).f1_macro
            f1_validacao = Avaliacao.medir(
                dados.y[validacao], self.prever_em(modelo, dados.x_ajustado(validacao)), bloco=validacao
            ).f1_macro

            # Tamanho do modelo, para o relatório: árvores (rodadas × classes), folhas e nós de todas elas.
            arvores, folhas, nos = self._tamanho(modelo)
            linhas.append(
                {
                    "n_estimators": n_arvores,
                    "learning_rate": taxa,
                    "max_depth": profundidade,
                    "arvores": arvores,
                    "folhas_total": folhas,
                    "nos_total": nos,
                    "f1_macro_treino": f1_treino,
                    "f1_macro_validacao": f1_validacao,
                }
            )

        self.busca = pd.DataFrame(linhas)
        self.tempos = pd.Series(tempos, index=self.busca.index)
        self.posicao_escolhida = self.escolher(self.busca)
        self.modelo = modelos[self.posicao_escolhida]
        return self

    @staticmethod
    def _ajustar(dados: DadosModelo, n_arvores: int, taxa: float, profundidade: int) -> XGBClassifier:
        """Cria um XGBoost com estes hiperparâmetros e o treina SÓ com o bloco de treino, sem parada antecipada."""
        treino, validacao = config.BLOCO_TREINO, config.BLOCO_VALIDACAO
        colunas = DadosModelo.colunas_ajustadas()
        X, y = dados.x_ajustado(treino), dados.y[treino]
        # Nenhuma linha da validação pode estar no `fit`: o índice de cada linha é o do Parquet e não se repete.
        assert X.index.intersection(dados.x_ajustado(validacao).index).empty, "o fit recebeu linhas da validação"
        # O `fit` recebeu exatamente as linhas do treino, nem mais nem menos (o mesmo N de `resumo`, como na árvore).
        assert len(X) == dados.resumo[treino]["n"], "o fit não recebeu exatamente as linhas do treino"

        # Peso por linha: o mesmo dicionário de classe da árvore ajustada e da floresta (SPEC-comparacao-modelos.md).
        pesos = y.map(config.VARIANTES_AJUSTE[config.MODELO_AJUSTADA]).to_numpy(dtype=float)
        assert not np.isnan(pesos).any(), "há classe do treino sem peso de classe"

        modelo = XGBClassifier(
            n_estimators=n_arvores,
            learning_rate=taxa,
            max_depth=profundidade,
            tree_method=config.TREE_METHOD_BOOSTING,
            random_state=config.SEMENTE,  # mesmo modelo a cada execução
            n_jobs=1,  # uma linha de execução: o resultado não depende de como o trabalho seria dividido
        )
        # Sem `eval_set` nem `early_stopping_rounds`: o modelo roda todas as rodadas pedidas (ver config.py).
        modelo.fit(X, y.map(CODIGO), sample_weight=pesos)

        # Sem parada antecipada, o número de rodadas é exatamente o pedido; as colunas são as 10 da ajustada.
        assert modelo.get_booster().num_boosted_rounds() == n_arvores, "o XGBoost não rodou todas as rodadas pedidas"
        assert list(modelo.feature_names_in_) == colunas, "o XGBoost foi treinado com outras colunas"
        return modelo

    @staticmethod
    def _tamanho(modelo: XGBClassifier) -> tuple[int, int, int]:
        """Quantas árvores, folhas e nós o modelo tem (cada linha de `trees_to_dataframe` é um nó)."""
        nos = modelo.get_booster().trees_to_dataframe()
        folhas = int((nos["Feature"] == "Leaf").sum())
        return int(nos["Tree"].nunique()), folhas, len(nos)

    @staticmethod
    def prever_em(modelo: XGBClassifier, X: pd.DataFrame) -> pd.Series:
        """Classe prevista de cada linha de X como TEXTO (OK, RISCO ou FALHA), com o mesmo índice do `y`."""
        codigos = modelo.predict(X).astype(int)  # 0, 1 ou 2, na ordem de `config.CLASSES`
        return pd.Series(np.array(CLASSE)[codigos], index=X.index, dtype=object)

    def prever(self, X: pd.DataFrame) -> pd.Series:
        """Previsão do modelo escolhido para um X de 10 colunas."""
        return self.prever_em(self.modelo, X)

    @staticmethod
    def escolher(busca: pd.DataFrame) -> int:
        """Índice (em `busca`) do modelo escolhido: a regra da Tarefa 4, a mesma de `comparacao.escolher_por_regra`."""
        return escolher_por_regra(busca, ORDEM_SIMPLICIDADE)

    def quadro_busca(self) -> pd.DataFrame:
        """A busca como vai para o CSV: o modelo na frente, o escolhido marcado e as métricas arredondadas."""
        quadro = self.busca.round({"f1_macro_treino": config.CASAS_CSV, "f1_macro_validacao": config.CASAS_CSV})
        quadro.insert(0, "modelo", config.MODELO_BOOSTING)
        quadro["escolhida"] = quadro.index == self.posicao_escolhida
        return quadro

    def verificar(self, dados: DadosModelo) -> None:
        """Checagens do modelo escolhido; as do `fit` (só o treino, rodadas pedidas, colunas) ficam em `_ajustar`."""
        colunas = DadosModelo.colunas_ajustadas()

        # A grade inteira, sem repetir nenhuma combinação.
        esperadas = len(config.GRADE_ARVORES_BOOSTING) * len(config.GRADE_TAXA_APRENDIZADO_BOOSTING) * len(
            config.GRADE_PROFUNDIDADE_BOOSTING
        )
        assert len(self.busca) == len(self.busca[COMBINACAO].drop_duplicates()) == esperadas, (
            f"a busca do XGBoost não tem as {esperadas} combinações"
        )

        # O modelo guardado é o da linha escolhida, com as 10 colunas e o `max_depth` pedido.
        escolhida = self.busca.loc[self.posicao_escolhida]
        pedido = (escolhida["n_estimators"], escolhida["learning_rate"], escolhida["max_depth"])
        assert (self.modelo.n_estimators, self.modelo.learning_rate, self.modelo.max_depth) == pedido, (
            "o modelo guardado não é o da linha escolhida"
        )
        assert list(self.modelo.feature_names_in_) == colunas, "o modelo guardado tem outras colunas"
        assert not set(colunas) & set(config.COLUNAS_PROIBIDAS), "coluna proibida no X do XGBoost"

        # A regra de escolha, conferida por outro caminho (um laço, sem ordenar): o escolhido está dentro da tolerância
        # e nenhum modelo MAIS SIMPLES que ele está.
        melhor = self.busca["f1_macro_validacao"].max()
        limite = melhor - config.TOLERANCIA_ESCOLHA
        assert escolhida["f1_macro_validacao"] >= limite, "o escolhido está fora da tolerância"

        def simplicidade(linha: pd.Series) -> tuple:
            return (linha["n_estimators"], linha["max_depth"], -linha["learning_rate"])

        for _, linha in self.busca.iterrows():
            if simplicidade(linha) < simplicidade(escolhida):
                assert linha["f1_macro_validacao"] < limite, (
                    f"há modelo mais simples dentro da tolerância: {dict(linha[COMBINACAO])}"
                )

        # Mesma semente = mesmas previsões e mesmo F1: treina o escolhido de novo, à parte, e mede na validação.
        validacao = config.BLOCO_VALIDACAO
        X_validacao, y_validacao = dados.x_ajustado(validacao), dados.y[validacao]
        outro = self._ajustar(dados, int(pedido[0]), float(pedido[1]), int(pedido[2]))
        previsto_outro = self.prever_em(outro, X_validacao)
        assert previsto_outro.equals(self.prever(X_validacao)), "treinar de novo com a mesma semente deu previsões diferentes"
        # A busca guarda o F1 sem arredondar: o refeito tem de bater com ele até a tolerância da métrica.
        f1_refeito = Avaliacao.medir(y_validacao, previsto_outro, bloco=validacao).f1_macro
        assert abs(f1_refeito - escolhida["f1_macro_validacao"]) <= config.TOLERANCIA_METRICA, (
            f"F1 do escolhido refeito ({f1_refeito:.9f}) não bate com a busca ({escolhida['f1_macro_validacao']:.9f})"
        )
