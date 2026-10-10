"""Gera as figuras do guia para o artigo (docs/guia_para_o_artigo.md) a partir dos CSVs já gravados.

Nada é recalculado aqui: cada número vem de um arquivo de `data/modelo/comparacao/`, `data/modelo/teste/` ou
`data/analise_piso_regra3/`. As figuras 01 a 08 são da validação; as figuras 09 a 11 mostram o teste (aberto uma vez,
em 10/10/2026) ao lado da validação.

Uso (a partir da raiz do projeto; o matplotlib não é dependência do projeto):
    uv run --with matplotlib python docs/figuras_artigo/gerar_figuras.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines
import matplotlib.patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
COMPARACAO = RAIZ / "data" / "modelo" / "comparacao"
ANALISE_PISO = RAIZ / "data" / "analise_piso_regra3"
TESTE = RAIZ / "data" / "modelo" / "teste"
SAIDA = Path(__file__).resolve().parent

# Paleta de dados validada (slots 1, 2, 3 e 7 da paleta de referência) e tinta de texto; a persistência fica em cinza.
AZUL, LARANJA, AQUA, VIOLETA, CINZA = "#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#9b9a95"
TINTA, TINTA_2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"

# Um modelo = uma cor, em todas as figuras (a cor segue a entidade).
NOMES = {
    "persistencia": "Persistência\n(repete o agora)",
    "arvore_oficial": "Árvore\n(Tarefa 3)",
    "ajustada_com_peso": "Árvore\najustada",
    "random_forest": "Random\nForest",
    "xgboost": "XGBoost",
}
NOMES_LINHA = {chave: valor.replace("\n", " ") for chave, valor in NOMES.items()}
CORES = {
    "persistencia": CINZA,
    "arvore_oficial": VIOLETA,
    "ajustada_com_peso": AZUL,
    "random_forest": LARANJA,
    "xgboost": AQUA,
}

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "text.color": TINTA,
        "axes.edgecolor": GRADE,
        "axes.labelcolor": TINTA_2,
        "xtick.color": TINTA_2,
        "ytick.color": TINTA_2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "savefig.facecolor": "#fcfcfb",
    }
)


def salvar(figura: plt.Figure, nome: str) -> None:
    figura.savefig(SAIDA / nome, dpi=160, bbox_inches="tight")
    plt.close(figura)
    print("gravado:", nome)


def f1_macro() -> None:
    """01: F1 macro dos cinco modelos na validação."""
    tabela = pd.read_csv(COMPARACAO / "comparacao_modelos.csv").set_index("modelo")
    ordem = ["persistencia", "arvore_oficial", "ajustada_com_peso", "random_forest", "xgboost"]
    valores = [tabela.loc[m, "f1_macro"] for m in ordem]
    figura, eixo = plt.subplots(figsize=(8, 4.2))
    barras = eixo.barh([NOMES_LINHA[m] for m in ordem], valores, color=[CORES[m] for m in ordem], height=0.62)
    eixo.invert_yaxis()
    eixo.set_xlim(0.55, 0.73)
    eixo.xaxis.grid(True, color=GRADE)
    eixo.set_axisbelow(True)
    for barra, valor in zip(barras, valores):
        eixo.text(valor + 0.002, barra.get_y() + barra.get_height() / 2, f"{valor:.3f}".replace(".", ","), va="center")
    eixo.set_xlabel(
        "F1 macro na validação (quanto maior, melhor)\nO eixo começa em 0,55 para as diferenças aparecerem: "
        "compare os números, não o tamanho das barras."
    )
    eixo.set_title("Todos ganham da persistência e ficam muito próximos entre si", loc="left", fontsize=12)
    salvar(figura, "01_f1_macro.png")


def intervalos() -> None:
    """02: diferenças de F1 macro entre pares, com o IC 95 % por fluxo."""
    tabela = pd.read_csv(COMPARACAO / "ic_pareado.csv")
    rotulo = {
        ("random_forest", "persistencia"): "Random Forest − persistência",
        ("xgboost", "persistencia"): "XGBoost − persistência",
        ("random_forest", "ajustada_com_peso"): "Random Forest − árvore ajustada",
        ("xgboost", "ajustada_com_peso"): "XGBoost − árvore ajustada",
        ("xgboost", "random_forest"): "XGBoost − Random Forest",
    }
    ordem = list(rotulo)
    linhas = [tabela[(tabela.modelo == m) & (tabela.referencia == r)].iloc[0] for m, r in ordem]
    figura, eixo = plt.subplots(figsize=(8, 3.8))
    for posicao, linha in enumerate(linhas):
        cor = LARANJA if linha.modelo == "random_forest" else AQUA
        eixo.plot([linha.ic_inferior, linha.ic_superior], [posicao, posicao], color=cor, lw=2.5, solid_capstyle="round")
        eixo.plot(linha.diferenca_f1, posicao, "o", color=cor, markersize=9, markeredgecolor="#fcfcfb", markeredgewidth=2)
        eixo.text(linha.ic_superior + 0.003, posicao, f"{linha.diferenca_f1:+.3f}".replace(".", ","), va="center", fontsize=10)
    eixo.axvline(0, color=TINTA_2, lw=1)
    eixo.set_yticks(range(len(ordem)), [rotulo[o] for o in ordem])
    eixo.invert_yaxis()
    eixo.set_xlim(-0.02, 0.1)
    eixo.xaxis.grid(True, color=GRADE)
    eixo.set_axisbelow(True)
    eixo.set_xlabel("Diferença de F1 macro (ponto = estimativa, linha = IC 95 % por fluxo)")
    eixo.set_title("Só o ganho sobre a persistência tem prova; entre os três, o intervalo cruza o zero", loc="left", fontsize=12)
    salvar(figura, "02_diferencas_com_intervalo.png")


def f1_por_classe() -> None:
    """03: F1 por classe, um grupo por classe."""
    tabela = pd.read_csv(COMPARACAO / "comparacao_modelos.csv").set_index("modelo")
    modelos = ["persistencia", "ajustada_com_peso", "random_forest", "xgboost"]
    classes = ["OK", "RISCO", "FALHA"]
    largura = 0.2
    figura, eixo = plt.subplots(figsize=(8.5, 4.4))
    for i, modelo in enumerate(modelos):
        valores = [tabela.loc[modelo, f"f1_{c}"] for c in classes]
        posicoes = np.arange(3) + (i - 1.5) * largura
        eixo.bar(posicoes, valores, width=largura - 0.02, color=CORES[modelo], label=NOMES_LINHA[modelo])
        for x, v in zip(posicoes, valores):
            eixo.text(x, v + 0.012, f"{v:.2f}".replace(".", ","), ha="center", fontsize=8)
    eixo.set_xticks(range(3), classes)
    eixo.set_ylim(0, 1.05)
    eixo.yaxis.grid(True, color=GRADE)
    eixo.set_axisbelow(True)
    eixo.set_ylabel("F1 da classe (validação)")
    eixo.legend(ncols=4, loc="upper center", bbox_to_anchor=(0.5, -0.1), frameon=False, fontsize=9)
    eixo.set_title("OK é fácil para todos; RISCO e FALHA é onde os modelos se separam um pouco", loc="left", fontsize=12)
    salvar(figura, "03_f1_por_classe.png")


def desenhar_matriz(eixo, matriz: np.ndarray, titulo: str) -> None:
    """Uma matriz de confusão 3×3: a cor é a proporção da linha e o número é a contagem."""
    classes = ["OK", "RISCO", "FALHA"]
    proporcao = matriz / matriz.sum(axis=1, keepdims=True)
    eixo.imshow(proporcao, cmap="Blues", vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            eixo.text(j, i, f"{matriz[i, j]:,}".replace(",", "."), ha="center", va="center",
                      color="white" if proporcao[i, j] > 0.55 else TINTA, fontsize=11)
    eixo.set_xticks(range(3), classes)
    eixo.set_yticks(range(3), classes)
    eixo.set_xlabel("Previsto (daqui a ~12 min)")
    eixo.set_ylabel("O que aconteceu")
    eixo.set_title(titulo, fontsize=11)
    for lado in eixo.spines.values():
        lado.set_visible(False)


def matriz_de(tabela: pd.DataFrame, modelo: str) -> np.ndarray:
    classes = ["OK", "RISCO", "FALHA"]
    sub = tabela[tabela.modelo == modelo].set_index("verdadeiro").loc[classes]
    return sub[[f"previsto_{c}" for c in classes]].to_numpy()


def matrizes() -> None:
    """04: matriz de confusão (contagens) da persistência e da Random Forest na validação, lado a lado."""
    tabela = pd.read_csv(COMPARACAO / "matriz_comparacao.csv")
    figura, eixos = plt.subplots(1, 2, figsize=(10, 4.3))
    for eixo, modelo in zip(eixos, ["persistencia", "random_forest"]):
        desenhar_matriz(eixo, matriz_de(tabela, modelo), NOMES_LINHA[modelo])
    figura.suptitle("Matriz de confusão na validação: a cor é a proporção da linha, o número é a contagem",
                    x=0.02, ha="left", fontsize=12)
    figura.tight_layout()
    salvar(figura, "04_matriz_persistencia_vs_floresta.png")


def antecipar_falha() -> None:
    """05: quanto cada modelo acerta quando o estado agora é OK e daqui a 12 min é FALHA."""
    tabela = pd.read_csv(COMPARACAO / "comparacao_modelos.csv").set_index("modelo")
    ordem = ["persistencia", "arvore_oficial", "ajustada_com_peso", "random_forest", "xgboost"]
    valores = [tabela.loc[m, "acerto_OK_para_FALHA"] * 100 for m in ordem]
    figura, eixo = plt.subplots(figsize=(8, 4))
    barras = eixo.barh([NOMES_LINHA[m] for m in ordem], valores, color=[CORES[m] for m in ordem], height=0.62)
    eixo.invert_yaxis()
    eixo.set_xlim(0, 100)
    eixo.xaxis.grid(True, color=GRADE)
    eixo.set_axisbelow(True)
    for barra, valor in zip(barras, valores):
        eixo.text(valor + 1, barra.get_y() + barra.get_height() / 2, f"{valor:.1f} %".replace(".", ","), va="center")
    eixo.set_xlabel("% de acerto nos 201 casos em que o fluxo estava OK e virou FALHA 12 min depois")
    eixo.set_title("Prever o começo de uma falha continua difícil: nenhum modelo passa de 20 %", loc="left", fontsize=12)
    salvar(figura, "05_antecipar_o_inicio_da_falha.png")


def busca() -> None:
    """06: cada combinação de hiperparâmetros testada: F1 na validação × tamanho do modelo."""
    floresta = pd.read_csv(COMPARACAO / "busca_floresta.csv")
    boosting = pd.read_csv(COMPARACAO / "busca_boosting.csv")
    figura, eixo = plt.subplots(figsize=(8.5, 4.6))
    for dados, cor, nome in [(floresta, LARANJA, "Random Forest (32 testes)"), (boosting, AQUA, "XGBoost (16 testes)")]:
        eixo.scatter(dados.nos_total, dados.f1_macro_validacao, s=46, color=cor, edgecolor="#fcfcfb", linewidth=1.5,
                     label=nome, zorder=3)
        escolhida = dados[dados.escolhida]
        eixo.scatter(escolhida.nos_total, escolhida.f1_macro_validacao, s=170, facecolor="none", edgecolor=TINTA,
                     linewidth=1.8, zorder=4)
    melhor = max(floresta.f1_macro_validacao.max(), boosting.f1_macro_validacao.max())
    eixo.axhspan(melhor - 0.005, melhor, color=GRADE, alpha=0.7, zorder=1)
    eixo.set_xlim(1800, 2.5e5)
    eixo.set_xscale("log")
    eixo.set_xlabel("Tamanho do modelo (nós somados de todas as árvores, escala logarítmica)")
    eixo.set_ylabel("F1 macro na validação")
    eixo.yaxis.grid(True, color=GRADE)
    eixo.set_axisbelow(True)
    manipuladores, legendas = eixo.get_legend_handles_labels()
    manipuladores.append(matplotlib.patches.Patch(color=GRADE, label="faixa de empate (até 0,005 do melhor)"))
    manipuladores.append(
        matplotlib.lines.Line2D([], [], marker="o", linestyle="", markerfacecolor="none", markeredgecolor=TINTA,
                                markersize=11, label="escolhido dentro de cada família")
    )
    eixo.legend(handles=manipuladores, loc="lower right", frameon=False, fontsize=9)
    eixo.set_title("Modelos bem maiores quase não melhoram: o desempenho encosta num teto",
                   loc="left", fontsize=12)
    salvar(figura, "06_busca_de_hiperparametros.png")


def importancias() -> None:
    """07: importância das colunas na Random Forest, com nomes em linguagem simples."""
    tabela = pd.read_csv(COMPARACAO / "importancias.csv")
    tabela = tabela[tabela.modelo == "random_forest"].sort_values("importancia")
    legivel = {
        "n5_moderado": "Quantas das últimas 5 medições\nestavam em nível moderado",
        "aumento_pct": "Aumento do RTT sobre o normal do fluxo (%)",
        "media5_z": "Desvio médio das últimas 5 medições",
        "z_robusto": "Desvio da medição atual (z robusto)",
        "min5_z": "Menor desvio nas últimas 5 medições",
        "n5_aumento80": "Quantas das últimas 5 passaram\nde 80 % de aumento",
        "jitter_relativo": "Jitter relativo ao normal do fluxo",
        "n5_timeout": "Timeouts nas últimas 5 medições",
        "perda_pct": "Perda de pacotes (%)",
        "timeout_atual": "Timeout na medição atual",
    }
    figura, eixo = plt.subplots(figsize=(8.5, 5))
    eixo.barh([legivel[c] for c in tabela.coluna], tabela.importancia * 100, color=LARANJA, height=0.64)
    for y, v in enumerate(tabela.importancia * 100):
        eixo.text(v + 0.5, y, f"{v:.1f} %".replace(".", ","), va="center", fontsize=9)
    eixo.xaxis.grid(True, color=GRADE)
    eixo.set_axisbelow(True)
    eixo.set_xlabel("Importância na Random Forest (soma = 100 %)")
    eixo.set_title("O que a floresta olha: o histórico recente pesa mais que a medição isolada", loc="left", fontsize=12)
    salvar(figura, "07_importancia_das_colunas.png")


def piso() -> None:
    """08: o que o piso de 30 % fez com o rótulo: composição do alvo antes e depois."""
    tabela = pd.read_csv(ANALISE_PISO / "classes_no_modelo.csv")
    tabela = tabela[tabela.bloco == "treino+validacao"].set_index(["versao", "classe"])["fracao"] * 100
    figura, eixo = plt.subplots(figsize=(8, 3.4))
    cores = {"OK": "#c9c8c1", "RISCO": "#eda100", "FALHA": "#e34948"}
    for linha, versao, nome in [(1, "antes", "Regra da RFC\nsem piso"), (0, "depois", "Com piso de 30 %\nna regra de FALHA")]:
        inicio = 0
        for classe in ["OK", "RISCO", "FALHA"]:
            valor = tabela[(versao, classe)]
            eixo.barh(linha, valor, left=inicio, color=cores[classe], height=0.55, edgecolor="#fcfcfb", linewidth=2)
            texto = f"{classe}\n{valor:.1f} %".replace(".", ",")
            if valor < 8:  # segmento estreito: o rótulo fica ao lado, fora da barra
                eixo.text(101, linha, texto, ha="left", va="center", fontsize=9)
            else:
                eixo.text(inicio + valor / 2, linha, texto, ha="center", va="center", fontsize=9)
            inicio += valor
    eixo.set_yticks([1, 0], ["Regra da RFC\nsem piso", "Com piso de 30 %\nna regra de FALHA"])
    eixo.set_xlim(0, 112)
    eixo.set_xticks([0, 20, 40, 60, 80, 100])
    eixo.set_xlabel("% das medições que o modelo aprende (treino + validação)")
    eixo.spines["left"].set_visible(False)
    eixo.set_title("Com o piso, FALHA deixa de ser quase um quarto do alvo e passa a ser 5 %", loc="left", fontsize=12)
    salvar(figura, "08_efeito_do_piso_no_rotulo.png")


def precisao_falha(matriz: np.ndarray) -> float:
    return matriz[2, 2] / matriz[:, 2].sum()


def validacao_vs_teste() -> None:
    """09: as métricas da Random Forest e da persistência na validação e no teste."""
    comparacao = pd.read_csv(COMPARACAO / "comparacao_modelos.csv").set_index("modelo")
    matriz_val = pd.read_csv(COMPARACAO / "matriz_comparacao.csv")
    teste = pd.read_csv(TESTE / "metricas_teste.csv")

    def do_teste(modelo: str, metrica: str, classe: str) -> float:
        return float(teste[(teste.modelo == modelo) & (teste.metrica == metrica) & (teste.classe == classe)].valor.iloc[0])

    nomes = ["F1 macro", "F1 de FALHA", "Recall de FALHA", "Precisão de FALHA"]
    modelos = ["persistencia", "random_forest"]
    valores = {"Validação (13.490 medições)": {}, "Teste (20.507 medições)": {}}
    for modelo in modelos:
        valores["Validação (13.490 medições)"][modelo] = [
            comparacao.loc[modelo, "f1_macro"], comparacao.loc[modelo, "f1_FALHA"],
            comparacao.loc[modelo, "recall_FALHA"], precisao_falha(matriz_de(matriz_val, modelo)),
        ]
        valores["Teste (20.507 medições)"][modelo] = [
            do_teste(modelo, "f1_macro", "todas"), do_teste(modelo, "f1", "FALHA"),
            do_teste(modelo, "recall", "FALHA"), do_teste(modelo, "precisao", "FALHA"),
        ]
    figura, eixos = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for eixo, (titulo, por_modelo) in zip(eixos, valores.items()):
        for i, modelo in enumerate(modelos):
            posicoes = np.arange(4) + (i - 0.5) * 0.36
            eixo.bar(posicoes, por_modelo[modelo], width=0.34, color=CORES[modelo], label=NOMES_LINHA[modelo])
            for x, v in zip(posicoes, por_modelo[modelo]):
                eixo.text(x, v + 0.012, f"{v:.2f}".replace(".", ","), ha="center", fontsize=8.5)
        eixo.set_xticks(range(4), [n.replace(" de ", "\nde ") for n in nomes], fontsize=9)
        eixo.set_title(titulo, loc="left", fontsize=11)
        eixo.set_ylim(0, 1.0)
        eixo.yaxis.grid(True, color=GRADE)
        eixo.set_axisbelow(True)
    eixos[0].legend(loc="upper left", frameon=False, fontsize=9, ncols=2)
    figura.suptitle("A floresta acerta mais quando avisa FALHA, mas no teste encontra menos falhas que a persistência",
                    x=0.02, ha="left", fontsize=12)
    figura.tight_layout()
    salvar(figura, "09_validacao_vs_teste.png")


def matriz_teste() -> None:
    """10: matriz de confusão da persistência e da Random Forest no teste."""
    tabela = pd.read_csv(TESTE / "matriz_teste.csv")
    figura, eixos = plt.subplots(1, 2, figsize=(10, 4.3))
    for eixo, modelo in zip(eixos, ["persistencia", "random_forest"]):
        desenhar_matriz(eixo, matriz_de(tabela, modelo), NOMES_LINHA[modelo])
    figura.suptitle("Matriz de confusão no teste: a cor é a proporção da linha, o número é a contagem",
                    x=0.02, ha="left", fontsize=12)
    figura.tight_layout()
    salvar(figura, "10_matriz_teste.png")


def ganho_validacao_vs_teste() -> None:
    """11: o ganho de F1 macro da Random Forest sobre a persistência, com IC 95 % por fluxo, na validação e no teste."""
    validacao = pd.read_csv(COMPARACAO / "ic_pareado.csv")
    validacao = validacao[(validacao.modelo == "random_forest") & (validacao.referencia == "persistencia")].iloc[0]
    teste = pd.read_csv(TESTE / "ic_ganho_teste.csv").iloc[0]
    figura, eixo = plt.subplots(figsize=(8, 2.6))
    for posicao, (nome, linha) in enumerate([("Validação", validacao), ("Teste", teste)]):
        eixo.plot([linha.ic_inferior, linha.ic_superior], [posicao, posicao], color=LARANJA, lw=2.5, solid_capstyle="round")
        eixo.plot(linha.diferenca_f1, posicao, "o", color=LARANJA, markersize=9, markeredgecolor="#fcfcfb", markeredgewidth=2)
        eixo.text(linha.ic_superior + 0.003, posicao, f"{linha.diferenca_f1:+.3f}".replace(".", ","), va="center")
        eixo.text(linha.diferenca_f1, posicao + 0.22, f"IC 95 %: [{linha.ic_inferior:+.3f}; {linha.ic_superior:+.3f}]".replace(".", ","),
                  ha="center", fontsize=8.5, color=TINTA_2)
    eixo.axvline(0, color=TINTA_2, lw=1)
    eixo.set_yticks([0, 1], ["Validação", "Teste (aberto uma vez)"])
    eixo.set_ylim(1.5, -0.5)  # a validação em cima, o teste embaixo
    eixo.set_xlim(-0.01, 0.1)
    eixo.xaxis.grid(True, color=GRADE)
    eixo.set_axisbelow(True)
    eixo.set_xlabel("Ganho de F1 macro da floresta sobre a persistência (ponto = estimativa, linha = IC 95 % por fluxo)")
    eixo.set_title("O ganho se manteve no teste, mas o intervalo chega mais perto do zero", loc="left", fontsize=12)
    salvar(figura, "11_ganho_validacao_vs_teste.png")


if __name__ == "__main__":
    f1_macro()
    intervalos()
    f1_por_classe()
    matrizes()
    antecipar_falha()
    busca()
    importancias()
    piso()
    validacao_vs_teste()
    matriz_teste()
    ganho_validacao_vs_teste()
