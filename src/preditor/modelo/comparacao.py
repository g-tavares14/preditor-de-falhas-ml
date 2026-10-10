"""Comparação das famílias: regra de escolha, IC pareado por fluxo e tabelas (SPEC-comparacao-modelos.md).

Só cálculo: recebe tabelas, matrizes e previsões, e devolve tabelas. Não treina e não grava nada; quem faz isso é
`execucao_comparacao.py`. Este módulo não importa `floresta.py` nem `boosting.py`: eles é que importam
`escolher_por_regra` daqui (a mesma regra da Tarefa 4, sem alterar `ajuste.py`).
"""

import numpy as np
import pandas as pd

from preditor import config
from preditor.modelo.avaliacao import Mudanca, Resultado


def escolher_por_regra(tabela: pd.DataFrame, ordem: list[tuple[str, bool]], coluna_f1: str = "f1_macro_validacao") -> int:
    """Índice (em `tabela`) da escolhida: a mais simples entre as a até `TOLERANCIA_ESCOLHA` do maior F1 macro.

    `ordem` é a lista `[(coluna, crescente)]` da mais simples para a mais complexa. Quem chama confere que essa ordem
    é total (cada linha tem uma chave diferente); sem isso, a escolha dependeria da ordem das linhas.
    """
    melhor = tabela[coluna_f1].max()
    candidatas = tabela[tabela[coluna_f1] >= melhor - config.TOLERANCIA_ESCOLHA]
    colunas = [coluna for coluna, _ in ordem]
    crescente = [sentido for _, sentido in ordem]
    return int(candidatas.sort_values(colunas, ascending=crescente).index[0])


def f1_macro_das_matrizes(matrizes: np.ndarray) -> np.ndarray:
    """F1 macro de cada matriz 3×3 de um lote (eixo 0 = o lote; linha = verdadeiro, coluna = previsto), sem laço.

    A conta é a de `Avaliacao.verificar`: F1 = 2·acertos / (linha + coluna) e, quando o denominador é zero, F1 = 0.
    """
    matrizes = np.asarray(matrizes, dtype=float)
    acertos = np.diagonal(matrizes, axis1=1, axis2=2)  # verdadeiros positivos de cada classe
    denominador = matrizes.sum(axis=2) + matrizes.sum(axis=1)  # linha + coluna = 2·VP + FP + FN
    f1 = np.divide(2 * acertos, denominador, out=np.zeros_like(acertos), where=denominador > 0)
    return f1.mean(axis=1)  # média simples das 3 classes, como o F1 macro de sempre


def ic_pareado(
    verdadeiro: pd.Series,
    previstos: dict[str, pd.Series],
    fluxos: pd.Series,
    pares: list[tuple[str, str]],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """IC da diferença de F1 macro de cada par (a − b), por bootstrap de FLUXOS (SPEC-comparacao-modelos.md, item 2).

    Sorteia os fluxos com reposição (`IC_REAMOSTRAS` vezes, semente `SEMENTE`); uma reamostra leva todas as medições
    de cada fluxo sorteado, e um fluxo sorteado duas vezes entra duas vezes. Os modelos usam as MESMAS reamostras
    (comparação pareada). Devolve a tabela do IC e o F1 macro de cada modelo na validação inteira.
    """
    codigo = {classe: indice for indice, classe in enumerate(config.CLASSES)}
    assert all(previsto.index.equals(verdadeiro.index) for previsto in previstos.values()), (
        "os modelos precisam ter previsto as mesmas linhas da validação"
    )
    assert fluxos.index.equals(verdadeiro.index), "fluxos e verdadeiro com linhas diferentes"

    # Cada linha vira (fluxo, classe verdadeira, classe prevista) em números: a matriz de cada fluxo sai de um bincount.
    nomes_fluxo, codigo_fluxo = np.unique(fluxos.to_numpy(), return_inverse=True)
    n_fluxos = len(nomes_fluxo)
    y = verdadeiro.map(codigo).to_numpy()
    por_fluxo = {}  # modelo → matriz 3×3 de cada fluxo: (fluxo, verdadeiro, previsto)
    for nome, previsto in previstos.items():
        p = previsto.map(codigo).to_numpy()
        contagem = np.bincount(codigo_fluxo * 9 + y * 3 + p, minlength=n_fluxos * 9)
        por_fluxo[nome] = contagem.reshape(n_fluxos, 3, 3)

    # Sorteio: `vezes[b, f]` = quantas vezes o fluxo f entrou na reamostra b. Cada reamostra tem F sorteios.
    rng = np.random.default_rng(config.SEMENTE)
    sorteados = rng.integers(0, n_fluxos, size=(config.IC_REAMOSTRAS, n_fluxos))
    vezes = np.stack([np.bincount(linha, minlength=n_fluxos) for linha in sorteados])
    assert (vezes.sum(axis=1) == n_fluxos).all(), "uma reamostra não tem F sorteios de fluxo"

    # A matriz de cada reamostra é a soma das matrizes dos fluxos, ponderada por `vezes`.
    matrizes = {nome: np.einsum("bf,fij->bij", vezes, m) for nome, m in por_fluxo.items()}
    # Conta de conservação: a reamostra tem as medições de cada fluxo sorteado, nem mais nem menos.
    linhas_por_fluxo = next(iter(por_fluxo.values())).sum(axis=(1, 2))
    for nome, m in matrizes.items():
        assert (m.sum(axis=(1, 2)) == vezes @ linhas_por_fluxo).all(), f"{nome}: a reamostra não soma as linhas sorteadas"

    f1_reamostra = {nome: f1_macro_das_matrizes(m) for nome, m in matrizes.items()}
    f1_pontual = {nome: float(f1_macro_das_matrizes(m.sum(axis=0, keepdims=True))[0]) for nome, m in por_fluxo.items()}

    # Intervalo de confiança: os percentis das diferenças nas reamostras (com o nível de `IC_NIVEL`).
    cauda = (1 - config.IC_NIVEL) / 2
    linhas = []
    for a, b in pares:
        diferencas = f1_reamostra[a] - f1_reamostra[b]
        inferior, superior = np.quantile(diferencas, [cauda, 1 - cauda])
        linhas.append(
            {
                "modelo": a,
                "referencia": b,
                "diferenca_f1": f1_pontual[a] - f1_pontual[b],  # na validação inteira, sem reamostrar
                "ic_inferior": float(inferior),
                "ic_superior": float(superior),
                # O intervalo não cruza o zero: só nesse caso a diferença tem prova de ser maior que o ruído.
                "exclui_zero": bool(inferior > 0 or superior < 0),
                "reamostras": config.IC_REAMOSTRAS,
                "fluxos": n_fluxos,
            }
        )
    return pd.DataFrame(linhas), f1_pontual


def quadro_comparacao(
    resultados: dict[str, Resultado],
    mudancas: dict[str, Mudanca],
    tamanhos: dict[str, tuple[int | None, int | None, int | None]],
    escolhido: str,
) -> pd.DataFrame:
    """As 5 linhas da comparação (SPEC-comparacao-modelos.md, "Estrutura"): métricas, transições e tamanho.

    `tamanhos` é (árvores, folhas, nós) de cada modelo; a persistência não é árvore e fica vazia. Sem tempo: tempo muda
    a cada execução e vai para `tempos.csv`, para este arquivo sair igual em duas execuções.
    """
    linhas = []
    for modelo, resultado in resultados.items():
        mudanca = mudancas[modelo]
        por_classe = resultado.por_classe
        transicoes = mudanca.transicoes.set_index(["atual", "futuro"])
        arvores, folhas, nos = tamanhos[modelo]
        linhas.append(
            {
                "modelo": modelo,
                "papel": "referencia" if modelo in (config.MODELO_PERSISTENCIA, config.MODELO_ARVORE) else "candidato",
                "f1_macro": resultado.f1_macro,
                "f1_OK": por_classe.loc["OK", "f1"],
                "f1_RISCO": por_classe.loc["RISCO", "f1"],
                "f1_FALHA": por_classe.loc["FALHA", "f1"],
                "recall_FALHA": por_classe.loc["FALHA", "recall"],
                "recall_RISCO": por_classe.loc["RISCO", "recall"],
                # "Onde erra" pela transição (agora → futuro): OK → FALHA é a queda que o modelo deveria antecipar;
                # FALHA → OK é o pico isolado que some em 12 min (o caso da regra 3 do rótulo).
                "n_OK_para_FALHA": int(transicoes.loc[("OK", "FALHA"), "n"]),
                "acerto_OK_para_FALHA": transicoes.loc[("OK", "FALHA"), "acerto"],
                "n_FALHA_para_OK": int(transicoes.loc[("FALHA", "OK"), "n"]),
                "acerto_FALHA_para_OK": transicoes.loc[("FALHA", "OK"), "acerto"],
                "acerto_futuro_igual": mudanca.acerto_igual,
                "acerto_futuro_muda": mudanca.acerto_muda,
                "arvores": arvores,
                "folhas": folhas,
                "nos": nos,
                "escolhido": modelo == escolhido,
            }
        )
    quadro = pd.DataFrame(linhas)
    # Inteiros que aceitam vazio (a persistência não tem árvores).
    for coluna in ("arvores", "folhas", "nos"):
        quadro[coluna] = quadro[coluna].astype("Int64")
    # Métricas com `CASAS_CSV` casas, como nos outros CSVs da validação.
    floats = quadro.select_dtypes(include="float").columns
    return quadro.round({coluna: config.CASAS_CSV for coluna in floats})


def quadro_importancias(importancias: dict[str, pd.Series]) -> pd.DataFrame:
    """Importância de cada coluna do X em cada modelo (formato longo: modelo, coluna, importância)."""
    linhas = []
    for modelo, serie in importancias.items():
        for coluna, valor in serie.items():
            linhas.append((modelo, coluna, round(float(valor), config.CASAS_CSV)))
    return pd.DataFrame(linhas, columns=["modelo", "coluna", "importancia"])
