"""Árvore de decisão oficial e a de contraste: busca na grade, treino e regras em texto (SPEC-arvore.md).

As regras em português ficam em `regras.py`.

Uma árvore CART (scikit-learn) aprende só com o treino; a validação decide qual das 28 combinações de
hiperparâmetros fica. Valores ausentes (`NaN`) entram como estão: o `DecisionTreeClassifier` do scikit-learn >= 1.4
os aceita na divisão, então nada é preenchido (RFC §8.3).
"""

import itertools
import re

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text

from preditor import config
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.dados import DadosModelo


class ArvoreBase:
    """O que a árvore oficial e a de contraste têm em comum: treino, previsão e leitura da árvore treinada.

    Só os métodos que servem às duas. Busca na grade, JSON de parâmetros e CSV da busca são só da oficial (`Arvore`).
    """

    def __init__(self) -> None:
        self.modelo: DecisionTreeClassifier | None = None  # a árvore treinada
        self.profundidade_pedida = 0  # `max_depth`
        self.folha_minima = 0  # `min_samples_leaf`

    @staticmethod
    def _ajustar(
        dados: DadosModelo,
        profundidade: int,
        folha_minima: int,
        *,
        contraste: bool = False,
        ajustado: bool = False,
        criterio: str = config.CRITERIO,
        peso: dict[str, float] | None = None,
    ) -> DecisionTreeClassifier:
        """Cria uma árvore com estes hiperparâmetros e a treina SÓ com o bloco de treino.

        Com `contraste`, o X é o da árvore de contraste (as 8 colunas, `rtt` e as regiões); o resto é igual.
        Com `ajustado`, o X é o da árvore ajustada da Tarefa 4 (as 8 colunas e as de `COLUNAS_AJUSTE`); só ela passa
        também `criterio` e `peso`. Sem esses argumentos, a árvore é a da Tarefa 3: Gini, sem peso, 8 colunas.
        """
        assert not (contraste and ajustado), "o X é o do contraste ou o do ajuste, nunca os dois"
        if contraste:
            X, colunas = dados.x_contraste(config.BLOCO_TREINO), dados.colunas_contraste()
        elif ajustado:
            X, colunas = dados.x_ajustado(config.BLOCO_TREINO), dados.colunas_ajustadas()
        else:
            X, colunas = dados.X[config.BLOCO_TREINO], config.COLUNAS_ARVORE
        y = dados.y[config.BLOCO_TREINO]
        # Nenhuma linha da validação pode estar no `fit`: o índice de cada linha é o do Parquet e não se repete.
        assert X.index.intersection(dados.X[config.BLOCO_VALIDACAO].index).empty, "o fit recebeu linhas da validação"

        modelo = DecisionTreeClassifier(
            criterion=criterio,
            max_depth=profundidade,
            min_samples_leaf=folha_minima,
            random_state=config.SEMENTE,  # mesma árvore a cada execução
            # Na Tarefa 3, sem `class_weight` (decisão do dono, 01/10/2026): `peso` fica `None`.
            # Só a árvore ajustada da Tarefa 4 passa um peso (SPEC-ajuste-arvore.md).
            class_weight=peso,
        )
        modelo.fit(X, y)

        # O nó raiz conta as linhas que o `fit` realmente viu: tem de ser o N do treino, nem mais nem menos.
        assert modelo.tree_.n_node_samples[0] == len(X) == dados.resumo[config.BLOCO_TREINO]["n"], (
            "o fit não viu exatamente as linhas do treino"
        )
        assert list(modelo.feature_names_in_) == colunas, "a árvore foi treinada com outras colunas"
        return modelo

    @staticmethod
    def _prever(modelo: DecisionTreeClassifier, X: pd.DataFrame) -> pd.Series:
        """Classe prevista de cada linha de X, com o mesmo índice (para comparar com o `y` linha a linha)."""
        return pd.Series(modelo.predict(X), index=X.index)

    def prever(self, X: pd.DataFrame) -> pd.Series:
        return self._prever(self.modelo, X)

    def divisoes_iniciais(self) -> list[str]:
        """As divisões dos primeiros `config.NIVEIS_DIVISOES` níveis, lidas de `modelo.tree_`."""
        arvore = self.modelo.tree_
        linhas: list[str] = []

        def descrever(no: int, nivel: int, resposta: str) -> None:
            recuo = "    " * (nivel - 1)
            n = arvore.n_node_samples[no]  # linhas de treino que chegam a este nó
            if arvore.children_left[no] == -1:  # -1 = não tem filho: é folha
                classe = self.modelo.classes_[np.argmax(arvore.value[no])]
                linhas.append(f"{recuo}{resposta}folha {classe}  (N = {n})")
                return
            coluna = self.modelo.feature_names_in_[arvore.feature[no]]
            linhas.append(f"{recuo}{resposta}{coluna} <= {arvore.threshold[no]:.2f} ?  (N = {n})")
            if nivel < config.NIVEIS_DIVISOES:
                # Esquerda = condição verdadeira ("sim"), direita = falsa ("não").
                descrever(arvore.children_left[no], nivel + 1, "sim: ")
                descrever(arvore.children_right[no], nivel + 1, "não: ")

        descrever(0, 1, "")
        return linhas

    def regras_texto(self) -> str:
        """A árvore inteira em texto, com o nome das colunas (as mesmas que o scikit-learn viu no `fit`)."""
        return export_text(self.modelo, feature_names=list(self.modelo.feature_names_in_))

    def estrutura(self, modelo: DecisionTreeClassifier | None = None) -> dict[str, np.ndarray]:
        """Cópia dos campos que definem a árvore (divisões, filhos, contagens): para comparar antes e depois."""
        arvore = (modelo or self.modelo).tree_
        # `missing_go_to_left` diz para que lado vai o valor ausente em cada divisão (`regras.py` o lê).
        campos = ("feature", "threshold", "children_left", "children_right", "missing_go_to_left", "n_node_samples", "value")
        return {campo: np.array(getattr(arvore, campo)) for campo in campos}

    @staticmethod
    def exigir_mesma_estrutura(a: dict[str, np.ndarray], b: dict[str, np.ndarray], quando: str) -> None:
        for campo in a:
            assert np.array_equal(a[campo], b[campo]), f"{quando}: a árvore mudou (campo `{campo}`)"

    @staticmethod
    def verificar_regras(texto: str, permitidas: list[str] = config.COLUNAS_ARVORE) -> None:
        """Confere que o texto das regras só cita as colunas `permitidas` e classes de `CLASSES`."""
        # Cada divisão do `export_text` tem a forma "|--- coluna <= limiar" ou "|--- coluna >  limiar".
        # O nome pode ter espaço (colunas de região, como "América do Norte"): `.+?` pega até o sinal.
        citadas = set(re.findall(r"\|--- (.+?) +(?:<=|>) ", texto))
        assert citadas, "as regras em texto não têm nenhuma divisão"
        fora = citadas - set(permitidas)
        assert not fora, f"as regras citam colunas fora das permitidas: {sorted(fora)}"
        classes = set(re.findall(r"\|--- class: (\w+)", texto))
        assert classes <= set(config.CLASSES), f"as regras citam classes fora de {config.CLASSES}: {sorted(classes)}"


class Arvore(ArvoreBase):
    """A árvore oficial: busca na grade e escolha pela validação."""

    def __init__(self) -> None:
        super().__init__()
        self.busca = pd.DataFrame()  # as 28 combinações, da melhor para a pior (primeira linha = escolhida)

    def buscar(self, dados: DadosModelo) -> "Arvore":
        """Treina as 28 árvores no treino, mede cada uma na validação e guarda a de maior F1 macro."""
        treino, validacao = config.BLOCO_TREINO, config.BLOCO_VALIDACAO
        linhas = []
        modelos = {}  # (max_depth, min_samples_leaf) → árvore treinada

        for profundidade, folha_minima in itertools.product(config.GRADE_PROFUNDIDADE, config.GRADE_FOLHA_MINIMA):
            modelo = self._ajustar(dados, profundidade, folha_minima)
            modelos[(profundidade, folha_minima)] = modelo

            # O F1 macro de treino só serve para ver o quanto a árvore decora o treino (compare com o da
            # validação). A escolha usa apenas a validação.
            f1_treino = Avaliacao.medir(
                dados.y[treino], self._prever(modelo, dados.X[treino]), bloco=treino
            ).f1_macro
            f1_validacao = Avaliacao.medir(
                dados.y[validacao], self._prever(modelo, dados.X[validacao]), bloco=validacao
            ).f1_macro

            linhas.append(
                {
                    "max_depth": profundidade,
                    "min_samples_leaf": folha_minima,
                    "profundidade_obtida": int(modelo.tree_.max_depth),  # pode ser menor que a pedida
                    "folhas": int(modelo.tree_.n_leaves),
                    "f1_macro_treino": f1_treino,
                    "f1_macro_validacao": f1_validacao,
                }
            )

        # Critério de escolha (SPEC-arvore.md): maior F1 macro na validação; empate → a mais rasa
        # (`max_depth` menor), depois a de folha maior (`min_samples_leaf` maior). Cada combinação aparece uma
        # vez, então esta ordenação é total e a primeira linha é a escolhida, sem sorteio.
        self.busca = (
            pd.DataFrame(linhas)
            .sort_values(
                ["f1_macro_validacao", "max_depth", "min_samples_leaf"], ascending=[False, True, False]
            )
            .reset_index(drop=True)
        )
        melhor = self.busca.iloc[0]
        self.profundidade_pedida = int(melhor["max_depth"])
        self.folha_minima = int(melhor["min_samples_leaf"])
        self.modelo = modelos[(self.profundidade_pedida, self.folha_minima)]
        return self

    def descricao(self) -> dict:
        """O que vai para `arvore_oficial.json`: os hiperparâmetros pedidos e o que a árvore realmente ficou."""
        return {
            "criterio": config.CRITERIO,
            "max_depth_pedido": self.profundidade_pedida,
            "min_samples_leaf_pedido": self.folha_minima,
            "profundidade_obtida": int(self.modelo.tree_.max_depth),
            "folhas": int(self.modelo.tree_.n_leaves),
            "semente": config.SEMENTE,
            "class_weight": self.modelo.class_weight,  # None: sem balanceamento
            "colunas": list(config.COLUNAS_ARVORE),
        }

    def quadro_busca(self) -> pd.DataFrame:
        """A tabela da busca como vai para o CSV: mesma ordem, métricas com `CASAS_CSV` casas."""
        return self.busca.round({"f1_macro_treino": config.CASAS_CSV, "f1_macro_validacao": config.CASAS_CSV})

    def verificar(self, dados: DadosModelo) -> None:
        """Checagens da árvore escolhida; as do `fit` ficam em `_ajustar`."""
        # 28 combinações, sem repetir nenhuma.
        esperadas = len(config.GRADE_PROFUNDIDADE) * len(config.GRADE_FOLHA_MINIMA)
        chaves = self.busca[["max_depth", "min_samples_leaf"]].drop_duplicates()
        assert len(self.busca) == len(chaves) == esperadas, f"a busca não tem as {esperadas} combinações"

        self.verificar_regras(self.regras_texto())

        # Treinar de novo com a mesma semente tem de dar exatamente a mesma árvore: mesmas divisões
        # (coluna e limiar de cada nó), mesmos filhos, mesmas contagens por classe e o mesmo texto.
        outra = self._ajustar(dados, self.profundidade_pedida, self.folha_minima)
        self.exigir_mesma_estrutura(self.estrutura(), self.estrutura(outra), "treinar de novo com a mesma semente")
        assert export_text(outra, feature_names=config.COLUNAS_ARVORE) == self.regras_texto(), (
            "o texto da árvore mudou ao treinar de novo"
        )


class ArvoreContraste(ArvoreBase):
    """Árvore de contraste (SPEC-arvore.md; diário da Tarefa 3, seção 4): NÃO é o modelo do projeto.

    Mesmo treino, mesmo alvo e mesmos hiperparâmetros da oficial (sem nova busca), com as 8 colunas mais `rtt` e a
    região. Só serve para ver o que a árvore faz quando enxerga a distância. Herda de `ArvoreBase` só o que lê a
    árvore treinada; não tem busca, JSON de parâmetros nem regras em português (a oficial é quem os tem).
    """

    def treinar(self, oficial: Arvore, dados: DadosModelo) -> "ArvoreContraste":
        # Os hiperparâmetros são os da oficial: o contraste muda só as colunas, nunca a busca.
        self.profundidade_pedida = oficial.profundidade_pedida
        self.folha_minima = oficial.folha_minima
        self.modelo = self._ajustar(dados, self.profundidade_pedida, self.folha_minima, contraste=True)
        return self

    def importancias_extras(self) -> pd.Series:
        """Importância (`feature_importances_`, soma 1 na árvore toda) de `rtt` e de cada coluna de região."""
        todas = pd.Series(self.modelo.feature_importances_, index=list(self.modelo.feature_names_in_))
        return todas[~todas.index.isin(config.COLUNAS_ARVORE)]

    def nivel_da_primeira_divisao(self, coluna: str) -> int | None:
        """Menor nível (raiz = 1) em que algum nó divide por `coluna`; `None` se ela não aparece na árvore."""
        arvore = self.modelo.tree_
        indice = list(self.modelo.feature_names_in_).index(coluna)
        achados = []

        def descer(no: int, nivel: int) -> None:
            if arvore.children_left[no] == -1:  # folha: não divide por nenhuma coluna
                return
            if arvore.feature[no] == indice:
                achados.append(nivel)
            descer(arvore.children_left[no], nivel + 1)
            descer(arvore.children_right[no], nivel + 1)

        descer(0, 1)
        return min(achados) if achados else None

    def verificar_contraste(self, dados: DadosModelo, oficial: Arvore, estrutura_oficial_antes: dict[str, np.ndarray]) -> None:
        """Checagens da árvore de contraste (as do `fit` ficam em `_ajustar`)."""
        # X do contraste = exatamente as 8 colunas + `rtt` + as colunas de região do treino, no treino e na validação.
        esperadas = (
            config.COLUNAS_ARVORE
            + [config.COLUNA_RTT_CONTRASTE]
            + [config.PREFIXO_REGIAO + regiao for regiao in dados.regioes]
        )
        assert list(self.modelo.feature_names_in_) == esperadas, "o contraste foi treinado com outras colunas"
        for bloco in (config.BLOCO_TREINO, config.BLOCO_VALIDACAO):
            assert list(dados.x_contraste(bloco).columns) == esperadas, f"{bloco}: X do contraste com colunas diferentes"
        # Mesmos hiperparâmetros da oficial: nada foi buscado de novo.
        assert (self.modelo.max_depth, self.modelo.min_samples_leaf) == (oficial.profundidade_pedida, oficial.folha_minima)

        # As regras em texto só citam as colunas do X do contraste.
        self.verificar_regras(self.regras_texto(), permitidas=esperadas)

        # Mesma semente, mesma árvore.
        outra = self._ajustar(dados, self.profundidade_pedida, self.folha_minima, contraste=True)
        self.exigir_mesma_estrutura(self.estrutura(), self.estrutura(outra), "retreinar o contraste com a mesma semente")

        # Treinar o contraste não pode ter mexido na oficial: a estrutura dela é a de antes.
        self.exigir_mesma_estrutura(estrutura_oficial_antes, oficial.estrutura(), "árvore oficial depois do contraste")
