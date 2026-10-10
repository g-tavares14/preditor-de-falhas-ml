"""Random Forest da comparação de modelos: busca na grade, escolha pela validação (SPEC-comparacao-modelos.md).

Usa o mesmo X da árvore ajustada (as 10 colunas de `DadosModelo.x_ajustado`), o mesmo peso de classe e a mesma semente.
A grade é treinada SÓ no treino e cada floresta é medida na validação. A escolha segue a regra da Tarefa 4 (a até
`TOLERANCIA_ESCOLHA` do maior F1 macro da validação, vence a mais simples). A regra está copiada aqui por composição:
`ajuste.py` não muda, para a saída do `ajuste` continuar igual byte a byte.

Não herda `ArvoreBase`: aquela classe é de árvore única (`DecisionTreeClassifier`, `tree_`). Reutiliza `DadosModelo` e
`Avaliacao` sem alterá-los.
"""

import itertools
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from preditor import config
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.comparacao import escolher_por_regra
from preditor.modelo.dados import DadosModelo

# As colunas que identificam uma combinação da grade (cada uma aparece uma vez na busca).
COMBINACAO = ["n_estimators", "max_depth", "min_samples_leaf"]
# A ordem de simplicidade da Random Forest, do mais simples para o mais complexo: menos árvores; depois, mais rasa;
# depois, folha mínima maior (menos folhas). Cada combinação aparece uma vez: a ordem é total, sem sorteio.
ORDEM_SIMPLICIDADE = [("n_estimators", True), ("max_depth", True), ("min_samples_leaf", False)]


class Floresta:
    """A Random Forest da comparação: `buscar` treina a grade, mede cada floresta e guarda a escolhida."""

    def __init__(self) -> None:
        self.modelo: RandomForestClassifier | None = None  # a floresta escolhida, treinada só no treino
        self.busca = pd.DataFrame()  # uma linha por floresta, na ordem da grade
        # Segundos de treino de cada linha de `busca`. Ficam FORA da busca gravada: o tempo muda a cada execução
        # e o `comparar` precisa gravar arquivos idênticos quando roda duas vezes.
        self.tempos = pd.Series(dtype="float64")
        self.posicao_escolhida = -1  # índice da escolhida em `busca`

    def buscar(self, dados: DadosModelo) -> "Floresta":
        """Treina as florestas da grade no treino, mede cada uma na validação e guarda a escolhida pela regra."""
        treino, validacao = config.BLOCO_TREINO, config.BLOCO_VALIDACAO
        linhas = []
        tempos = []
        modelos = []  # na mesma ordem de `linhas`

        grade = itertools.product(
            config.GRADE_ARVORES_FLORESTA, config.GRADE_PROFUNDIDADE_FLORESTA, config.GRADE_FOLHA_MINIMA_FLORESTA
        )
        for n_arvores, profundidade, folha_minima in grade:
            # Só o `fit` entra na conta do tempo: a medição de F1 logo abaixo não é treino.
            inicio = time.perf_counter()
            modelo = self._ajustar(dados, n_arvores, profundidade, folha_minima)
            tempos.append(time.perf_counter() - inicio)
            modelos.append(modelo)

            # Como na árvore ajustada: o F1 de treino só mostra o quanto a floresta decora o treino; a escolha usa a
            # validação.
            f1_treino = Avaliacao.medir(
                dados.y[treino], self.prever_em(modelo, dados.x_ajustado(treino)), bloco=treino
            ).f1_macro
            f1_validacao = Avaliacao.medir(
                dados.y[validacao], self.prever_em(modelo, dados.x_ajustado(validacao)), bloco=validacao
            ).f1_macro

            linhas.append(
                {
                    "n_estimators": n_arvores,
                    "max_depth": profundidade,
                    "min_samples_leaf": folha_minima,
                    # Tamanho da floresta, para o relatório: o maior caminho e o total de nós e folhas de todas as árvores.
                    "profundidade_obtida": max(int(arvore.tree_.max_depth) for arvore in modelo.estimators_),
                    "folhas_total": sum(int(arvore.tree_.n_leaves) for arvore in modelo.estimators_),
                    "nos_total": sum(int(arvore.tree_.node_count) for arvore in modelo.estimators_),
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
    def _ajustar(dados: DadosModelo, n_arvores: int, profundidade: int, folha_minima: int) -> RandomForestClassifier:
        """Cria uma floresta com estes hiperparâmetros e a treina SÓ com o bloco de treino."""
        treino, validacao = config.BLOCO_TREINO, config.BLOCO_VALIDACAO
        colunas = DadosModelo.colunas_ajustadas()
        X, y = dados.x_ajustado(treino), dados.y[treino]
        # Nenhuma linha da validação pode estar no `fit`: o índice de cada linha é o do Parquet e não se repete.
        assert X.index.intersection(dados.x_ajustado(validacao).index).empty, "o fit recebeu linhas da validação"

        modelo = RandomForestClassifier(
            n_estimators=n_arvores,
            max_depth=profundidade,
            min_samples_leaf=folha_minima,
            max_features=config.MAX_FEATURES_FLORESTA,  # `sqrt`: ~3 colunas por divisão (config.py, origem)
            criterion=config.CRITERIO,  # Gini, como na árvore oficial
            # O mesmo peso de classe da árvore ajustada adotada (SPEC-comparacao-modelos.md, suposição 3).
            class_weight=config.VARIANTES_AJUSTE[config.MODELO_AJUSTADA],
            random_state=config.SEMENTE,  # mesma floresta a cada execução
            n_jobs=1,  # uma linha de execução: o resultado não depende de como o trabalho seria dividido
        )
        modelo.fit(X, y)

        # O `fit` recebeu exatamente as linhas do treino, nem mais nem menos (o mesmo N de `resumo`, como na árvore).
        assert len(X) == dados.resumo[treino]["n"], "o fit não recebeu exatamente as linhas do treino"
        # A floresta tem o número de árvores pedido, todas com as 10 colunas da ajustada.
        assert len(modelo.estimators_) == n_arvores, f"a floresta tem {len(modelo.estimators_)} árvores, e não {n_arvores}"
        assert list(modelo.feature_names_in_) == colunas, "a floresta foi treinada com outras colunas"
        return modelo

    @staticmethod
    def prever_em(modelo: RandomForestClassifier, X: pd.DataFrame) -> pd.Series:
        """Classe prevista de cada linha de X (OK, RISCO ou FALHA), com o mesmo índice para comparar com o `y`."""
        return pd.Series(modelo.predict(X), index=X.index)

    def prever(self, X: pd.DataFrame) -> pd.Series:
        """Previsão da floresta escolhida para um X de 10 colunas."""
        return self.prever_em(self.modelo, X)

    @staticmethod
    def escolher(busca: pd.DataFrame) -> int:
        """Índice (em `busca`) da floresta escolhida: a regra da Tarefa 4, a mesma de `comparacao.escolher_por_regra`."""
        return escolher_por_regra(busca, ORDEM_SIMPLICIDADE)

    def quadro_busca(self) -> pd.DataFrame:
        """A busca como vai para o CSV: a floresta na frente, a escolhida marcada e as métricas arredondadas."""
        quadro = self.busca.round({"f1_macro_treino": config.CASAS_CSV, "f1_macro_validacao": config.CASAS_CSV})
        quadro.insert(0, "modelo", config.MODELO_FLORESTA)
        quadro["escolhida"] = quadro.index == self.posicao_escolhida
        return quadro

    def verificar(self, dados: DadosModelo) -> None:
        """Checagens da floresta escolhida; as do `fit` (só o treino, com N linhas) ficam em `_ajustar`."""
        colunas = DadosModelo.colunas_ajustadas()

        # A grade inteira, sem repetir nenhuma combinação.
        esperadas = (
            len(config.GRADE_ARVORES_FLORESTA) * len(config.GRADE_PROFUNDIDADE_FLORESTA) * len(config.GRADE_FOLHA_MINIMA_FLORESTA)
        )
        assert len(self.busca) == len(self.busca[COMBINACAO].drop_duplicates()) == esperadas, (
            f"a busca da floresta não tem as {esperadas} combinações"
        )

        # A floresta guardada é a da linha escolhida, com as 10 colunas, este peso e os critérios pedidos.
        escolhida = self.busca.loc[self.posicao_escolhida]
        pedido = (escolhida["n_estimators"], escolhida["max_depth"], escolhida["min_samples_leaf"])
        assert (self.modelo.n_estimators, self.modelo.max_depth, self.modelo.min_samples_leaf) == pedido, (
            "a floresta guardada não é a da linha escolhida"
        )
        assert list(self.modelo.feature_names_in_) == colunas, "a floresta guardada tem outras colunas"
        assert not set(colunas) & set(config.COLUNAS_PROIBIDAS), "coluna proibida no X da floresta"
        assert self.modelo.class_weight == config.VARIANTES_AJUSTE[config.MODELO_AJUSTADA], "peso de classe diferente da ajustada"
        assert self.modelo.criterion == config.CRITERIO and self.modelo.max_features == config.MAX_FEATURES_FLORESTA

        # A regra de escolha, conferida por outro caminho (um laço, sem ordenar): a escolhida está dentro da tolerância
        # e nenhuma floresta MAIS SIMPLES que ela está.
        melhor = self.busca["f1_macro_validacao"].max()
        limite = melhor - config.TOLERANCIA_ESCOLHA
        assert escolhida["f1_macro_validacao"] >= limite, "a escolhida está fora da tolerância"

        def simplicidade(linha: pd.Series) -> tuple:
            return (linha["n_estimators"], linha["max_depth"], -linha["min_samples_leaf"])

        for _, linha in self.busca.iterrows():
            if simplicidade(linha) < simplicidade(escolhida):
                assert linha["f1_macro_validacao"] < limite, (
                    f"há floresta mais simples dentro da tolerância: {dict(linha[COMBINACAO])}"
                )

        # Mesma semente = mesmas previsões e mesmo F1: treina a escolhida de novo, à parte, e mede na validação.
        validacao = config.BLOCO_VALIDACAO
        X_validacao, y_validacao = dados.x_ajustado(validacao), dados.y[validacao]
        outra = self._ajustar(dados, int(pedido[0]), int(pedido[1]), int(pedido[2]))
        previsto_outra = outra.predict(X_validacao)
        assert np.array_equal(previsto_outra, self.prever(X_validacao).to_numpy()), (
            "treinar de novo com a mesma semente deu previsões diferentes"
        )
        # A busca guarda o F1 sem arredondar: a refeita tem de bater com ele até a tolerância da métrica.
        f1_refeito = Avaliacao.medir(
            y_validacao, pd.Series(previsto_outra, index=X_validacao.index), bloco=validacao
        ).f1_macro
        assert abs(f1_refeito - escolhida["f1_macro_validacao"]) <= config.TOLERANCIA_METRICA, (
            f"F1 da escolhida refeito ({f1_refeito:.9f}) não bate com a busca ({escolhida['f1_macro_validacao']:.9f})"
        )
