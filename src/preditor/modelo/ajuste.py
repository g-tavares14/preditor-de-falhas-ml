"""Árvore ajustada da Tarefa 4: busca com as colunas novas e escolha pela validação (SPEC-ajuste-arvore.md).

A árvore da Tarefa 3 (`arvore.py`) não muda. Esta usa as 8 colunas dela mais as de `config.COLUNAS_AJUSTE`, busca
também o critério (Gini ou entropia) e pode treinar com peso de classe. Entre as árvores quase empatadas em F1
macro, fica a mais simples (`ArvoreAjustada.escolher`).
"""

import itertools

import pandas as pd

from preditor import config
from preditor.modelo.arvore import ArvoreBase
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.dados import DadosModelo

# As colunas que identificam uma combinação da grade (cada uma aparece uma vez na busca de uma variante).
COMBINACAO = ["criterio", "max_depth", "min_samples_leaf"]


class ArvoreAjustada(ArvoreBase):
    """Uma variante da árvore ajustada: `nome` é o da coluna `modelo` dos CSVs; `peso` é o `class_weight` (ou None)."""

    def __init__(self, nome: str, peso: dict[str, float] | None) -> None:
        super().__init__()
        self.nome = nome
        self.peso = peso
        self.criterio = ""  # critério da escolhida
        self.busca = pd.DataFrame()  # todas as combinações, na ordem da grade
        self.posicao_escolhida = -1  # índice da escolhida em `busca`

    def buscar(self, dados: DadosModelo) -> "ArvoreAjustada":
        """Treina a grade inteira no treino, mede cada árvore na validação e guarda a escolhida pela regra."""
        treino, validacao = config.BLOCO_TREINO, config.BLOCO_VALIDACAO
        linhas = []
        modelos = []  # na mesma ordem de `linhas`

        grade = itertools.product(config.GRADE_CRITERIO_AJUSTE, config.GRADE_PROFUNDIDADE, config.GRADE_FOLHA_MINIMA)
        for criterio, profundidade, folha_minima in grade:
            modelo = self._ajustar(dados, profundidade, folha_minima, ajustado=True, criterio=criterio, peso=self.peso)
            modelos.append(modelo)

            # Como na Tarefa 3: o F1 de treino só mostra o quanto a árvore decora; a escolha usa a validação.
            f1_treino = Avaliacao.medir(
                dados.y[treino], self._prever(modelo, dados.x_ajustado(treino)), bloco=treino
            ).f1_macro
            f1_validacao = Avaliacao.medir(
                dados.y[validacao], self._prever(modelo, dados.x_ajustado(validacao)), bloco=validacao
            ).f1_macro
            linhas.append(
                {
                    "criterio": criterio,
                    "max_depth": profundidade,
                    "min_samples_leaf": folha_minima,
                    "profundidade_obtida": int(modelo.tree_.max_depth),  # pode ser menor que a pedida
                    "folhas": int(modelo.tree_.n_leaves),
                    "f1_macro_treino": f1_treino,
                    "f1_macro_validacao": f1_validacao,
                }
            )

        self.busca = pd.DataFrame(linhas)
        self.posicao_escolhida = self.escolher(self.busca)
        escolhida = self.busca.loc[self.posicao_escolhida]
        self.criterio = str(escolhida["criterio"])
        self.profundidade_pedida = int(escolhida["max_depth"])
        self.folha_minima = int(escolhida["min_samples_leaf"])
        self.modelo = modelos[self.posicao_escolhida]
        return self

    @staticmethod
    def ordem_de_simplicidade(busca: pd.DataFrame) -> pd.DataFrame:
        """A busca da árvore mais simples para a mais complexa: a ordem do desempate da regra de escolha."""
        # Mais simples = mais rasa; depois, folha mínima maior (menos folhas); depois, o critério que vem primeiro
        # na grade (Gini). Cada combinação aparece uma vez: a ordem é total, sem sorteio.
        posicao_criterio = busca["criterio"].map(config.GRADE_CRITERIO_AJUSTE.index)
        return (
            busca.assign(posicao_criterio=posicao_criterio)
            .sort_values(["max_depth", "min_samples_leaf", "posicao_criterio"], ascending=[True, False, True])
            .drop(columns="posicao_criterio")
        )

    @staticmethod
    def escolher(busca: pd.DataFrame) -> int:
        """Índice (em `busca`) da árvore escolhida: a mais simples entre as quase empatadas com a melhor.

        "Quase empatada" = F1 macro da validação a até `TOLERANCIA_ESCOLHA` do maior. Função pura: só lê a tabela.
        """
        melhor = busca["f1_macro_validacao"].max()
        candidatas = busca[busca["f1_macro_validacao"] >= melhor - config.TOLERANCIA_ESCOLHA]
        return int(ArvoreAjustada.ordem_de_simplicidade(candidatas).index[0])

    def prever_bloco(self, dados: DadosModelo, bloco: str) -> pd.Series:
        """Classe prevista para cada linha do bloco, com o X ajustado (as 10 colunas)."""
        return self.prever(dados.x_ajustado(bloco))

    def descricao(self) -> dict:
        """O que vai para `arvore_ajustada.json`: como a árvore foi pedida e como ela ficou."""
        return {
            "modelo": self.nome,
            "criterio": self.criterio,
            "max_depth_pedido": self.profundidade_pedida,
            "min_samples_leaf_pedido": self.folha_minima,
            "profundidade_obtida": int(self.modelo.tree_.max_depth),
            "folhas": int(self.modelo.tree_.n_leaves),
            "semente": config.SEMENTE,
            "class_weight": self.modelo.class_weight,  # None na variante sem peso
            "tolerancia_escolha": config.TOLERANCIA_ESCOLHA,
            "colunas": DadosModelo.colunas_ajustadas(),
        }

    def quadro_busca(self) -> pd.DataFrame:
        """A busca como vai para o CSV: a variante na frente, a escolhida marcada e as métricas arredondadas."""
        quadro = self.busca.round({"f1_macro_treino": config.CASAS_CSV, "f1_macro_validacao": config.CASAS_CSV})
        quadro.insert(0, "modelo", self.nome)
        quadro["escolhida"] = quadro.index == self.posicao_escolhida
        return quadro

    def verificar(self, dados: DadosModelo) -> None:
        """Checagens da variante; as do `fit` (só treino, colunas certas) ficam em `ArvoreBase._ajustar`."""
        colunas = DadosModelo.colunas_ajustadas()
        esperadas = len(config.GRADE_CRITERIO_AJUSTE) * len(config.GRADE_PROFUNDIDADE) * len(config.GRADE_FOLHA_MINIMA)
        assert len(self.busca) == len(self.busca[COMBINACAO].drop_duplicates()) == esperadas, (
            f"{self.nome}: a busca não tem as {esperadas} combinações"
        )

        # A árvore guardada é a da linha escolhida, treinada com as 10 colunas, este critério e este peso.
        assert list(self.modelo.feature_names_in_) == colunas, f"{self.nome}: treinada com outras colunas"
        assert not set(colunas) & set(config.COLUNAS_PROIBIDAS), f"{self.nome}: coluna proibida no X ajustado"
        assert self.modelo.class_weight == self.peso, f"{self.nome}: peso de classe diferente do pedido"
        escolhida = self.busca.loc[self.posicao_escolhida]
        pedido = (self.modelo.criterion, self.modelo.max_depth, self.modelo.min_samples_leaf)
        assert pedido == (escolhida["criterio"], escolhida["max_depth"], escolhida["min_samples_leaf"]), (
            f"{self.nome}: a árvore guardada não é a da linha escolhida"
        )

        # A regra de escolha, conferida por outro caminho (um laço, sem ordenar): a escolhida está dentro da
        # tolerância e nenhuma árvore MAIS SIMPLES que ela está.
        melhor = self.busca["f1_macro_validacao"].max()
        limite = melhor - config.TOLERANCIA_ESCOLHA
        assert escolhida["f1_macro_validacao"] >= limite, f"{self.nome}: a escolhida está fora da tolerância"

        def simplicidade(linha: pd.Series) -> tuple:
            return (linha["max_depth"], -linha["min_samples_leaf"], config.GRADE_CRITERIO_AJUSTE.index(linha["criterio"]))

        for _, linha in self.busca.iterrows():
            if simplicidade(linha) < simplicidade(escolhida):
                assert linha["f1_macro_validacao"] < limite, (
                    f"{self.nome}: há árvore mais simples dentro da tolerância: {dict(linha[COMBINACAO])}"
                )

        self.verificar_regras(self.regras_texto(), permitidas=colunas)

        # Mesma semente = mesma árvore.
        outra = self._ajustar(
            dados, self.profundidade_pedida, self.folha_minima, ajustado=True, criterio=self.criterio, peso=self.peso
        )
        self.exigir_mesma_estrutura(self.estrutura(), self.estrutura(outra), f"{self.nome}: treinar de novo com a mesma semente")
