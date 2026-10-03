"""Regras em português da árvore oficial: caminho raiz → folha, texto e verificação (SPEC-arvore.md, "Como a árvore é escolhida").

Cada regra é lida do caminho real em `modelo.tree_` (nada escrito à mão) e a checagem prova que o texto, aplicado
ao X, seleciona exatamente as linhas que `apply` põe na folha. Só a árvore oficial vira regras em português.
"""

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from preditor import config
from preditor.modelo.dados import BLOCOS_USADOS, DadosModelo


@dataclass(frozen=True)
class Condicao:
    """Uma divisão do caminho raiz → folha, com o limiar EXATO da árvore (a regra impressa o arredonda)."""

    coluna: str
    limiar: float
    menor_ou_igual: bool  # True: `coluna <= limiar` (filho da esquerda); False: `coluna > limiar` (direita)
    ausente_entra: bool  # o valor ausente (NaN) satisfaz esta condição? Vem de `tree_.missing_go_to_left`
    pode_ter_ausente: bool  # a coluna tem NaN no treino ou na validação: só então a regra precisa dizer para onde vai
    casas: int = config.CASAS_LIMIAR_REGRA  # casas decimais do limiar impresso (a árvore ajustada usa mais)

    def texto(self) -> str:
        sinal = "≤" if self.menor_ou_igual else ">"
        ausente = " (ou ausente)" if self.pode_ter_ausente and self.ausente_entra else ""
        return f"`{self.coluna}` {sinal} {_formatar_limiar(self.limiar, self.casas)}{ausente}"


@dataclass(frozen=True)
class Regra:
    """Uma folha lida como regra: o caminho da raiz até ela, a classe que ela prevê, N e pureza no treino."""

    folha: int  # número do nó em `tree_`
    classe: str
    n_treino: int  # linhas de treino que chegam à folha
    pureza: float  # fração delas que é da classe prevista
    condicoes: tuple[Condicao, ...]  # o caminho cru, na ordem da raiz à folha (pode repetir coluna e lado)
    fundidas: tuple[Condicao, ...]  # o mesmo caminho sem repetição: o que o texto imprime (ver `Regras.fundir`)

    def texto(self) -> str:
        condicoes = " e ".join(c.texto() for c in self.fundidas)
        return f"se {condicoes} então {self.classe}"


def _formatar_limiar(limiar: float, casas: int = config.CASAS_LIMIAR_REGRA) -> str:
    """Limiar para leitura: `casas` casas, sem zeros sobrando (mínimo de 2) e com vírgula."""
    inteiro, decimais = f"{limiar:.{casas}f}".split(".")
    return f"{inteiro},{decimais.rstrip('0').ljust(2, '0')}"


class Regras:
    @staticmethod
    def ler(
        modelo: DecisionTreeClassifier,
        dados: DadosModelo,
        X: dict[str, pd.DataFrame] | None = None,
        casas: int = config.CASAS_LIMIAR_REGRA,
    ) -> list[Regra]:
        """As folhas de treino mais cheias, uma por classe, lidas do caminho real raiz → folha de `tree_`.

        `X` (bloco → colunas) é o X com que `modelo` foi treinado; sem ele, o X oficial das 8 colunas. `casas` é o
        número de casas do limiar impresso. A árvore ajustada da Tarefa 4 passa os dela (SPEC-ajuste-arvore.md).
        """
        arvore = modelo.tree_
        X = dados.X if X is None else X
        y = dados.y[config.BLOCO_TREINO]
        folha_de_cada_linha = modelo.apply(X[config.BLOCO_TREINO])  # em que folha cada linha de treino cai

        # Só `NaN` em treino ou validação conta (o teste está fechado): é onde a regra precisa dizer o lado do ausente.
        com_ausente = {
            coluna for coluna in modelo.feature_names_in_ if any(X[bloco][coluna].isna().any() for bloco in BLOCOS_USADOS)
        }
        caminhos = Regras._caminhos(modelo, com_ausente, casas)

        # Classe de cada folha: a de maior proporção em `value`, como o `predict` faz.
        classe_da_folha = {folha: str(modelo.classes_[np.argmax(arvore.value[folha])]) for folha in caminhos}

        # Por classe, a folha com mais linhas de treino (empate: o menor número de nó, para não depender de sorteio).
        escolhidas: list[int] = []
        for classe in config.CLASSES:
            da_classe = [folha for folha in caminhos if classe_da_folha[folha] == classe]
            if da_classe:
                escolhidas.append(min(da_classe, key=lambda folha: (-arvore.n_node_samples[folha], folha)))
        # Se alguma classe não tiver folha, completa com as folhas mais cheias que ainda não foram escolhidas.
        sobras = sorted((f for f in caminhos if f not in escolhidas), key=lambda f: (-arvore.n_node_samples[f], f))
        escolhidas += sobras[: max(0, config.N_REGRAS_PORTUGUES - len(escolhidas))]

        regras = []
        for folha in escolhidas:
            classe = classe_da_folha[folha]
            linhas = folha_de_cada_linha == folha
            regras.append(
                Regra(
                    folha=int(folha),
                    classe=classe,
                    n_treino=int(linhas.sum()),
                    # Pureza = fração das linhas de treino da folha cuja classe verdadeira é a prevista.
                    pureza=float((y[linhas] == classe).mean()),
                    condicoes=tuple(caminhos[folha]),
                    fundidas=Regras.fundir(caminhos[folha]),
                )
            )
        return regras

    @staticmethod
    def fundir(caminho: list[Condicao]) -> tuple[Condicao, ...]:
        """Funde as condições repetidas do caminho: por coluna e por lado, só o limite mais apertado.

        O mesmo `>` repetido fica com o MAIOR limiar; o mesmo `≤`, com o MENOR. Uma coluna pode ficar com os
        dois lados (`x > a` e `x ≤ b`). A ordem é a da primeira aparição da coluna no caminho (e, dentro dela,
        a do lado). O valor ausente só passa pela coluna fundida se passava por TODAS as condições dela no
        caminho (ele precisa passar por todas para chegar à folha); por isso o "(ou ausente)" some se uma só
        condição da coluna o recusar, mesmo a do outro lado.
        """
        mais_apertada: dict[str, dict[bool, Condicao]] = {}  # coluna → lado (`≤`?) → condição de limite mais apertado
        ausente_passa: dict[str, bool] = {}  # coluna → todas as condições dela aceitam o ausente?
        for condicao in caminho:
            lados = mais_apertada.setdefault(condicao.coluna, {})  # dict mantém a ordem de inserção
            ausente_passa[condicao.coluna] = ausente_passa.get(condicao.coluna, True) and condicao.ausente_entra
            atual = lados.get(condicao.menor_ou_igual)
            mais_apertado = atual is None or (
                condicao.limiar < atual.limiar if condicao.menor_ou_igual else condicao.limiar > atual.limiar
            )
            if mais_apertado:
                lados[condicao.menor_ou_igual] = condicao  # troca o valor, mas a posição do lado não muda
        return tuple(
            replace(condicao, ausente_entra=ausente_passa[coluna])
            for coluna, lados in mais_apertada.items()
            for condicao in lados.values()
        )

    @staticmethod
    def _caminhos(
        modelo: DecisionTreeClassifier, com_ausente: set[str], casas: int = config.CASAS_LIMIAR_REGRA
    ) -> dict[int, list[Condicao]]:
        """Para cada folha, as condições do caminho da raiz até ela, lidas de `tree_` (nada escrito à mão)."""
        arvore = modelo.tree_
        caminhos: dict[int, list[Condicao]] = {}

        def descer(no: int, ate_aqui: list[Condicao]) -> None:
            esquerda, direita = arvore.children_left[no], arvore.children_right[no]
            if esquerda == -1:  # -1 = não tem filho: é folha
                caminhos[no] = ate_aqui
                return
            coluna = str(modelo.feature_names_in_[arvore.feature[no]])  # as colunas com que a árvore foi treinada
            limiar = float(arvore.threshold[no])  # exato: o `export_text` mostra só 2 casas
            # O `export_text` não diz para que lado vai o NaN em cada divisão; `missing_go_to_left` diz
            # (scikit-learn >= 1.3). Vale também para nós que não viram NaN no treino: o scikit-learn
            # manda o NaN para o filho com mais linhas.
            ausente_vai_esquerda = bool(arvore.missing_go_to_left[no])
            pode = coluna in com_ausente
            # Esquerda = `<=`, direita = `>`; o ausente entra na condição do lado para onde a árvore o manda.
            descer(esquerda, ate_aqui + [Condicao(coluna, limiar, True, ausente_vai_esquerda, pode, casas)])
            descer(direita, ate_aqui + [Condicao(coluna, limiar, False, not ausente_vai_esquerda, pode, casas)])

        descer(0, [])
        return caminhos

    @staticmethod
    def selecionar(condicoes: tuple[Condicao, ...], X: pd.DataFrame, *, limiar_impresso: bool = False) -> np.ndarray:
        """Quais linhas de X as condições selecionam: `True` onde TODAS valem (o caminho cru ou o fundido).

        Com `limiar_impresso`, usa o limiar arredondado como está no texto; sem ele, o limiar exato da árvore.
        """
        selecionadas = np.ones(len(X), dtype=bool)
        for condicao in condicoes:
            # O scikit-learn converte X para float32 antes de comparar com o limiar (float64): a regra
            # faz o mesmo, senão uma linha muito perto do limiar poderia cair do outro lado.
            valores = X[condicao.coluna].to_numpy(dtype=np.float32).astype(np.float64)
            limiar = round(condicao.limiar, condicao.casas) if limiar_impresso else condicao.limiar
            ausente = np.isnan(valores)
            if condicao.menor_ou_igual:
                vale = valores <= limiar  # NaN dá falso aqui
            else:
                vale = valores > limiar
            if condicao.ausente_entra:
                vale = vale | ausente
            selecionadas &= vale
        return selecionadas

    @staticmethod
    def verificar(
        modelo: DecisionTreeClassifier, regras: list[Regra], dados: DadosModelo, X: dict[str, pd.DataFrame] | None = None
    ) -> None:
        """Cada regra seleciona exatamente as linhas que `apply` põe na folha dela (treino e validação).

        `X` é o mesmo de `ler`: sem ele, o X oficial.
        """
        arvore = modelo.tree_
        X_por_bloco = dados.X if X is None else X
        colunas = set(modelo.feature_names_in_)
        assert 1 <= len(regras) <= config.N_REGRAS_PORTUGUES, f"número de regras inesperado: {len(regras)}"
        assert len({r.folha for r in regras}) == len(regras), "a mesma folha virou duas regras"

        for regra in regras:
            assert regra.fundidas, f"a regra da folha {regra.folha} não tem condição"
            Regras._verificar_fusao(regra)
            assert {c.coluna for c in regra.fundidas} <= colunas, f"regra cita coluna fora das colunas da árvore: {regra.texto()}"
            # `regra.classe` é a que `tree_` guarda para a folha, e a mais cheia entre as folhas da mesma classe.
            assert regra.classe == modelo.classes_[np.argmax(arvore.value[regra.folha])], "classe da regra ≠ classe da folha"
            assert regra.n_treino == arvore.n_node_samples[regra.folha], "N da regra ≠ n_node_samples da folha"
            mais_cheias = [
                f for f in range(arvore.node_count)
                if arvore.children_left[f] == -1 and modelo.classes_[np.argmax(arvore.value[f])] == regra.classe
            ]
            assert regra.n_treino == max(arvore.n_node_samples[f] for f in mais_cheias), (
                f"a regra da folha {regra.folha} não é a folha de treino mais cheia da classe {regra.classe}"
            )
            # Pureza conferida pelas proporções que a própria árvore guarda (soma 1 ou contagem: a razão é a mesma).
            proporcao = arvore.value[regra.folha][0]
            # Com peso de classe (árvore ajustada da Tarefa 4), `value` guarda as proporções PONDERADAS: dividir pelo
            # peso de cada classe devolve a proporção em linhas, que é o que a pureza mede. Sem peso, divide por 1.
            pesos_das_classes = modelo.class_weight or {}
            proporcao = proporcao / np.array([pesos_das_classes.get(classe, 1.0) for classe in modelo.classes_])
            indice = list(modelo.classes_).index(regra.classe)
            assert abs(regra.pureza - proporcao[indice] / proporcao.sum()) <= config.TOLERANCIA_METRICA, (
                f"pureza da regra {regra.folha} ≠ proporção de `tree_`"
            )

            for bloco in BLOCOS_USADOS:
                X = X_por_bloco[bloco]
                na_folha = modelo.apply(X) == regra.folha
                # O caminho cru, aplicado ao X com o limiar exato e o lado do ausente, é a folha...
                assert np.array_equal(Regras.selecionar(regra.condicoes, X), na_folha), (
                    f"{bloco}: o caminho da folha {regra.folha} não seleciona as linhas dessa folha"
                )
                # ...e a regra FUNDIDA (a que é impressa) também: a fusão não muda quais linhas entram.
                assert np.array_equal(Regras.selecionar(regra.fundidas, X), na_folha), (
                    f"{bloco}: a regra fundida da folha {regra.folha} não seleciona as linhas dessa folha"
                )
                # O texto arredondado, lido como está impresso, também (senão, aumente as casas do limiar).
                assert np.array_equal(Regras.selecionar(regra.fundidas, X, limiar_impresso=True), na_folha), (
                    f"{bloco}: o limiar impresso da regra {regra.folha} muda as linhas selecionadas"
                )
                if bloco == config.BLOCO_TREINO:
                    assert na_folha.sum() == regra.n_treino, "N da regra ≠ linhas de treino que `apply` põe na folha"

    @staticmethod
    def _verificar_fusao(regra: Regra) -> None:
        """Confere a fusão contra o caminho cru, condição por condição (os dados só pegam o que mexe em alguma linha)."""
        vistos = set()
        for fundida in regra.fundidas:
            chave = (fundida.coluna, fundida.menor_ou_igual)
            assert chave not in vistos, f"a regra da folha {regra.folha} repete {chave} depois de fundir"
            vistos.add(chave)
            do_lado = [c.limiar for c in regra.condicoes if (c.coluna, c.menor_ou_igual) == chave]
            apertado = min(do_lado) if fundida.menor_ou_igual else max(do_lado)  # `≤`: o menor; `>`: o maior
            assert fundida.limiar == apertado, f"folha {regra.folha}: limite de {chave} não é o mais apertado do caminho"
            da_coluna = [c.ausente_entra for c in regra.condicoes if c.coluna == fundida.coluna]
            assert fundida.ausente_entra == all(da_coluna), (
                f"folha {regra.folha}: o ausente em `{fundida.coluna}` não bate com as condições do caminho"
            )
        # Nenhum lado do caminho cru ficou de fora.
        assert vistos == {(c.coluna, c.menor_ou_igual) for c in regra.condicoes}, "a fusão perdeu um lado do caminho"

    @staticmethod
    def texto(regras: list[Regra]) -> str:
        """As regras como vão para a tela e para o fim de `regras_arvore_oficial.txt`."""
        linhas = [
            f"Regras em português: as folhas de treino mais cheias, uma por classe ({len(regras)} regras).",
            "Lidas do caminho real raiz → folha de `tree_`; N = linhas de treino da folha; pureza = fração delas da classe prevista.",
            "Condições repetidas do caminho foram fundidas: por coluna e por lado, fica só o limite mais apertado.",
            "(ou ausente) = o valor ausente também cai nesta condição; sem isso, ausente não passa por ela.",
            "",
        ]
        for numero, regra in enumerate(regras, start=1):
            acertos = round(regra.pureza * regra.n_treino)
            pureza = f"{regra.pureza:.1%}".replace(".", ",")  # vírgula, como o limiar
            linhas += [
                f"Regra {numero} (folha {regra.folha}, classe {regra.classe}):",
                f"  {regra.texto()}",
                f"  N de treino = {regra.n_treino}; pureza = {pureza} ({acertos} de {regra.n_treino} são {regra.classe})",
                "",
            ]
        return "\n".join(linhas)
