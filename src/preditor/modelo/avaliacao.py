"""Métricas de classificação na validação: a mesma conta para todo modelo (SPEC-arvore.md, "Leitura do erro").

Persistência, árvore oficial e árvore de contraste passam por `Avaliacao.medir`, sempre na ordem
`config.CLASSES` (OK, RISCO, FALHA). Assim os números são comparáveis lado a lado.
`Avaliacao.erros_concretos` escolhe, na validação, os dois erros da árvore que o dono lê linha a linha.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from preditor import config
from preditor.modelo.dados import BLOCOS_USADOS


@dataclass(frozen=True)
class Resultado:
    """Tudo o que `Avaliacao.medir` calcula para um modelo."""

    n: int  # linhas medidas
    matriz: pd.DataFrame  # 3×3 em contagem: linha = classe verdadeira, coluna = classe prevista
    por_classe: pd.DataFrame  # uma linha por classe; colunas: precisao, recall, f1, suporte
    f1_macro: float  # média simples dos 3 F1: cada classe pesa igual, mesmo a menor (RISCO)
    balanced_accuracy: float  # média dos 3 recalls
    acuracia: float  # só informativa: com classes desiguais (OK é a maioria), ela não decide nada


@dataclass(frozen=True)
class CasoErro:
    """O critério de um erro concreto (SPEC-arvore.md, "Leitura do erro"): qual linha da validação procurar."""

    titulo: str
    caminho_longo: bool  # True: mediana do fluxo acima da mediana das medianas; False: abaixo
    exige_estavel: bool  # True: só linhas com |z_robusto| <= `EXEMPLO_OK_Z_MAX`
    verdadeiro: str  # classe verdadeira (o alvo, `status_futuro`)
    previsto: str  # classe prevista pela árvore oficial
    maior_rtt: bool  # True: vence o maior `rtt`; False: o menor

    def descricao(self, mediana_das_medianas: float) -> str:
        partes = [
            f"mediana do fluxo {'>' if self.caminho_longo else '<'} mediana das medianas ({mediana_das_medianas:.2f} ms)"
        ]
        if self.exige_estavel:
            partes.append(f"|z_robusto| <= {config.EXEMPLO_OK_Z_MAX:g}")
        partes.append(f"verdadeiro {self.verdadeiro}, previsto {self.previsto}")
        return ", ".join(partes) + f"; o de {'MAIOR' if self.maior_rtt else 'MENOR'} rtt"


# Os dois casos da spec: o falso alarme de caminho longo e estável, e a FALHA de caminho curto que passou batida.
CASOS_ERRO = (
    CasoErro("Caminho longo e estável que a árvore mandou para FALHA", True, True, "OK", "FALHA", maior_rtt=True),
    CasoErro("FALHA de caminho curto que a árvore mandou para OK", False, False, "FALHA", "OK", maior_rtt=False),
)


@dataclass(frozen=True)
class ErroConcreto:
    """O que `Avaliacao.erros_concretos` achou para um caso."""

    caso: CasoErro
    candidatos: int  # quantas linhas da validação atendem ao critério
    linha: pd.Series | None  # a escolhida; None = o caso não apareceu na validação


class Avaliacao:
    @staticmethod
    def erros_concretos(
        X: pd.DataFrame,
        verdadeiro: pd.Series,
        previsto: pd.Series,
        status_atual: pd.Series,
        localizacao: pd.DataFrame,
        mediana_das_medianas: float,
    ) -> list[ErroConcreto]:
        """Um erro da árvore na validação para cada caso de `CASOS_ERRO`, escolhido sem sorteio.

        "Verdadeiro" é o alvo (`status_futuro`) e "previsto" é a previsão da árvore oficial.
        `localizacao` (`fluxo_id`, `t`, `rtt` e a mediana do fluxo) só localiza e classifica a linha:
        o X, com as 8 colunas, é o que a árvore viu e o que aparece como "métricas" na saída.
        """
        for nome, serie in (("verdadeiro", verdadeiro), ("previsto", previsto), ("status_atual", status_atual),
                            ("localizacao", localizacao)):
            assert serie.index.equals(X.index), f"{nome} e X precisam ser as mesmas linhas da validação"
        assert list(X.columns) == config.COLUNAS_ARVORE, "o X dos erros concretos tem de ter as 8 colunas da árvore"
        assert not set(localizacao.columns) & set(X.columns), "coluna de localização dentro do X"

        # Uma tabela só, de leitura: localização, mediana, as 8 métricas, status_atual e as duas classes.
        quadro = pd.concat([localizacao, X], axis=1)
        quadro["status_atual"] = status_atual
        quadro["verdadeiro"] = verdadeiro
        quadro["previsto"] = previsto

        erros = [Avaliacao._escolher(quadro, caso, mediana_das_medianas) for caso in CASOS_ERRO]
        for erro in erros:
            Avaliacao._verificar_erro(erro, quadro, mediana_das_medianas)
        return erros

    @staticmethod
    def _escolher(quadro: pd.DataFrame, caso: CasoErro, mediana_das_medianas: float) -> ErroConcreto:
        mediana = quadro[config.COLUNA_MEDIANA_FLUXO]
        # Caminho longo / curto = mediana do baseline do fluxo acima / abaixo da mediana das medianas
        # (premissa 4 da spec). Igual à mediana das medianas não é nenhum dos dois.
        criterio = (mediana > mediana_das_medianas) if caso.caminho_longo else (mediana < mediana_das_medianas)
        criterio &= (quadro["verdadeiro"] == caso.verdadeiro) & (quadro["previsto"] == caso.previsto)
        if caso.exige_estavel:
            # Estável = bem dentro do normal da rota. Sem RTT o `z_robusto` é nulo e a comparação dá falso.
            criterio &= quadro["z_robusto"].abs() <= config.EXEMPLO_OK_Z_MAX

        # Sem `rtt` não há como dizer "maior" nem "menor": linhas sem RTT (todos os pings em timeout) ficam fora.
        candidatas = quadro[criterio & quadro["rtt"].notna()]
        if candidatas.empty:
            return ErroConcreto(caso, candidatos=0, linha=None)
        # Lista ordenada: o `rtt` decide e, se empatar, `fluxo_id` e depois `t` (crescentes). A primeira linha vence.
        # `t` não se repete dentro de um fluxo (Silver), então a ordem é total: a escolha não depende de sorteio.
        ordenadas = candidatas.sort_values(
            ["rtt", "fluxo_id", "t"], ascending=[not caso.maior_rtt, True, True], kind="stable"
        )
        return ErroConcreto(caso, candidatos=len(ordenadas), linha=ordenadas.iloc[0])

    @staticmethod
    def _verificar_erro(erro: ErroConcreto, quadro: pd.DataFrame, mediana_das_medianas: float) -> None:
        """Confere a escolha por outro caminho: um laço comum de Python, linha a linha, sem `sort_values`."""
        caso = erro.caso
        chaves = []  # (chave de ordem, índice da linha) de cada linha que atende ao critério
        for indice, linha in quadro.iterrows():
            mediana = linha[config.COLUNA_MEDIANA_FLUXO]
            no_caminho = mediana > mediana_das_medianas if caso.caminho_longo else mediana < mediana_das_medianas
            if pd.isna(linha["rtt"]) or not no_caminho:
                continue
            if linha["verdadeiro"] != caso.verdadeiro or linha["previsto"] != caso.previsto:
                continue
            if caso.exige_estavel and not abs(linha["z_robusto"]) <= config.EXEMPLO_OK_Z_MAX:  # NaN também cai aqui
                continue
            # Chave: o `rtt` (com o sinal trocado quando se quer o maior), depois `fluxo_id`, depois `t`.
            chaves.append(((-linha["rtt"] if caso.maior_rtt else linha["rtt"], linha["fluxo_id"], linha["t"]), indice))

        assert erro.candidatos == len(chaves), (
            f"{caso.titulo}: {erro.candidatos} candidatas na escolha, mas {len(chaves)} na conferência"
        )
        if not chaves:
            assert erro.linha is None, f"{caso.titulo}: há linha escolhida, mas nenhuma candidata"
            return
        assert erro.linha is not None, f"{caso.titulo}: há candidatas, mas nada foi escolhido"
        assert erro.linha.name == min(chaves)[1], f"{caso.titulo}: a linha escolhida não é a primeira da lista ordenada"

    @staticmethod
    def medir(verdadeiro: pd.Series, previsto: pd.Series, *, bloco: str) -> Resultado:
        """Compara a classe verdadeira com a prevista, linha a linha, e confere as próprias contas."""
        # A barreira real contra medir o teste é `DadosModelo`: ele nunca guarda linhas do teste (só o N),
        # então não há o que passar para cá. Este `bloco` é um guarda contra erro de uso: quem chama diz de
        # onde vêm as linhas, e o teste (fechado até a Tarefa 5) é recusado pelo nome.
        # `treino` é aceito de propósito: a busca de hiperparâmetros mede também o F1 macro de treino
        # (para ver o quanto a árvore decora o treino). Só a validação decide a escolha.
        assert bloco in BLOCOS_USADOS, f"só se mede {BLOCOS_USADOS}; recebi o bloco {bloco!r}"

        # Entradas conferidas antes de qualquer conta: duas séries das mesmas linhas, sem ausentes, só com as 3 classes.
        assert len(verdadeiro) > 0, "nada para medir"
        assert verdadeiro.index.equals(previsto.index), "verdadeiro e previsto precisam ser as mesmas linhas"
        assert verdadeiro.notna().all() and previsto.notna().all(), "há classe ausente em verdadeiro ou previsto"
        fora = (set(verdadeiro) | set(previsto)) - set(config.CLASSES)
        assert not fora, f"classe fora de {config.CLASSES}: {sorted(fora)}"
        # Sem as 3 classes em `verdadeiro`, o recall da classe ausente seria 0/0 e a média macro enganaria.
        faltam = set(config.CLASSES) - set(verdadeiro)
        assert not faltam, f"falta classe em verdadeiro: {sorted(faltam)}"

        classes = list(config.CLASSES)

        # `labels` fixa a ordem das linhas e colunas: sem ele, o scikit-learn usaria ordem alfabética.
        contagem = confusion_matrix(verdadeiro, previsto, labels=classes)
        matriz = pd.DataFrame(contagem, index=classes, columns=classes)

        # `zero_division=0`: classe nunca prevista tem precisão 0 em vez de erro (o recall dela segue valendo).
        precisao, recall, f1, suporte = precision_recall_fscore_support(
            verdadeiro, previsto, labels=classes, zero_division=0
        )
        por_classe = pd.DataFrame(
            {"precisao": precisao, "recall": recall, "f1": f1, "suporte": suporte}, index=classes
        )

        resultado = Resultado(
            n=len(verdadeiro),
            matriz=matriz,
            por_classe=por_classe,
            f1_macro=f1_score(verdadeiro, previsto, labels=classes, average="macro", zero_division=0),
            balanced_accuracy=balanced_accuracy_score(verdadeiro, previsto),
            acuracia=accuracy_score(verdadeiro, previsto),
        )
        Avaliacao.verificar(resultado)
        return resultado

    @staticmethod
    def verificar(resultado: Resultado) -> None:
        """Refaz as contas só com a matriz (numpy, sem scikit-learn) e compara com o que foi calculado."""
        tol = config.TOLERANCIA_METRICA
        m = resultado.matriz.to_numpy(dtype=float)

        assert m.sum() == resultado.n, f"a matriz soma {m.sum():.0f}, mas N = {resultado.n}"

        acertos = np.diag(m)  # verdadeiro positivo de cada classe
        total_verdadeiro = m.sum(axis=1)  # linha: quantas linhas são da classe
        total_previsto = m.sum(axis=0)  # coluna: quantas linhas o modelo mandou para a classe

        # Divisão que devolve 0 quando o denominador é 0 (classe sem previsões, por exemplo).
        def dividir(numerador: np.ndarray, denominador: np.ndarray) -> np.ndarray:
            return np.divide(numerador, denominador, out=np.zeros_like(numerador), where=denominador > 0)

        precisao = dividir(acertos, total_previsto)
        recall = dividir(acertos, total_verdadeiro)
        # F1 = 2·VP / (2·VP + FP + FN) = 2·VP / (linha + coluna): é a média harmônica sem passar pela precisão.
        f1 = dividir(2 * acertos, total_verdadeiro + total_previsto)

        por_classe = resultado.por_classe
        assert np.allclose(por_classe["precisao"], precisao, atol=tol), "precisão não bate com a matriz"
        assert np.allclose(por_classe["recall"], recall, atol=tol), "recall não bate com a matriz"
        assert np.allclose(por_classe["f1"], f1, atol=tol), "F1 por classe não bate com a matriz"
        assert (por_classe["suporte"].to_numpy() == total_verdadeiro).all(), "suporte não bate com a soma das linhas"

        # O F1 macro é a média dos 3 F1 recalculados da matriz (não a média ponderada pelo suporte).
        assert abs(resultado.f1_macro - f1.mean()) <= tol, (
            f"F1 macro {resultado.f1_macro:.6f} diferente da média dos 3 F1 da matriz {f1.mean():.6f}"
        )
        assert abs(resultado.balanced_accuracy - recall.mean()) <= tol, "balanced accuracy não bate com a média dos recalls"
        assert abs(resultado.acuracia - acertos.sum() / resultado.n) <= tol, "acurácia não bate com a diagonal da matriz"

    @staticmethod
    def quadro_matriz(modelo: str, resultado: Resultado) -> pd.DataFrame:
        """A matriz em formato de CSV: uma linha por classe verdadeira, com o nome do modelo na frente."""
        quadro = resultado.matriz.add_prefix("previsto_")  # colunas: previsto_OK, previsto_RISCO, previsto_FALHA
        quadro.index.name = "verdadeiro"
        quadro = quadro.reset_index()
        quadro.insert(0, "modelo", modelo)
        return quadro

    @staticmethod
    def quadro_metricas(modelo: str, resultado: Resultado) -> pd.DataFrame:
        """As métricas em formato longo (modelo, metrica, classe, valor): acrescentar outro modelo é só empilhar."""
        linhas = []
        for classe, medidas in resultado.por_classe.iterrows():
            for metrica in ("precisao", "recall", "f1"):
                linhas.append((modelo, metrica, classe, medidas[metrica]))
        # As métricas que olham as 3 classes juntas não têm classe: `todas`.
        for metrica in ("f1_macro", "balanced_accuracy", "acuracia"):
            linhas.append((modelo, metrica, "todas", getattr(resultado, metrica)))
        quadro = pd.DataFrame(linhas, columns=["modelo", "metrica", "classe", "valor"])
        quadro["valor"] = quadro["valor"].round(config.CASAS_CSV)
        return quadro
