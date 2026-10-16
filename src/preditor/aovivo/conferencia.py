"""Conferências do serviço ao vivo (SPEC-ao-vivo.md, "Checagens"): a cópia em pandas contra o Gold, e o leitor contra o Silver.

`motor_contra_o_gold` é offline e roda em toda partida do serviço. `leitor_contra_o_silver` pede a API (rede) e roda em
`aovivo --conferir`. Qualquer diferença para o serviço com `AssertionError`/`SystemExit`: se o motor não reproduz o Gold,
a previsão ao vivo não é a do modelo que foi medido.

O teste não é lido para nada além da CONTAGEM de linhas: os valores comparados são só das linhas de treino e de validação.
"""

import numpy as np
import pandas as pd

from preditor import config
from preditor.aovivo import parametros
from preditor.aovivo.atlas import ClienteAtlas, ler_resultado
from preditor.aovivo.calculo import Baseline, Features, Rotulo
from preditor.modelo.dados import DadosModelo
from preditor.visualizacao.modelo_exportado import ModeloExportado

COLUNAS_FICHA_GOLD = ["n_medicoes", "n_validos", "mediana", "iqr", "jitter_tipico", "perda_tipica", "mad"]
COLUNAS_NUMERICAS = [
    "perda_pct", "timeout_atual", "z_robusto", "aumento_pct", "jitter_relativo", "moderado", "regra",
    *DadosModelo.colunas_ajustadas(),
]
COLUNAS_TEXTO = ["status_atual", "status_futuro"]


def _exigir_arquivos(*arquivos) -> None:
    faltando = [str(arquivo) for arquivo in arquivos if not arquivo.exists()]
    if faltando:
        raise SystemExit(f"Não encontrei {', '.join(faltando)}.\nRode antes: uv run python -m preditor gold")


def _iguais(a: pd.Series, b: pd.Series, relativa: float = parametros.TOLERANCIA, absoluta: float = parametros.TOLERANCIA) -> bool:
    """Iguais dentro da tolerância, e nulos nos mesmos lugares."""
    return bool(np.allclose(a.to_numpy(float), b.to_numpy(float), rtol=relativa, atol=absoluta, equal_nan=True))


def motor_contra_o_gold() -> None:
    """Baseline, X, regra, `status_atual` e `status_futuro` em pandas sobre o Silver = o Gold (treino e validação)."""
    _exigir_arquivos(config.ARQUIVO_SILVER, config.ARQUIVO_BASELINE, config.ARQUIVO_FEATURES, config.ARQUIVO_ROTULADO)
    silver = pd.read_parquet(config.ARQUIVO_SILVER, columns=["fluxo_id", "t", "rtt", "jitter", "perda_pct", "timeout_atual", "periodo"])

    # --- Baseline --------------------------------------------------------------------------------------------
    ficha = Baseline.calcular(silver[silver["periodo"] == "A"])
    gold_ficha = pd.read_parquet(config.ARQUIVO_BASELINE).set_index("fluxo_id")
    assert set(ficha.index) == set(gold_ficha.index), "o motor e o Gold têm fluxos diferentes no baseline"
    for coluna in COLUNAS_FICHA_GOLD:
        assert _iguais(ficha[coluna], gold_ficha[coluna].reindex(ficha.index)), f"baseline: a coluna {coluna} difere do Gold"
    assert (ficha["baseline_insuficiente"] == gold_ficha["baseline_insuficiente"].reindex(ficha.index)).all(), "baseline_insuficiente difere"

    # --- X e Y -----------------------------------------------------------------------------------------------
    rotulado = Rotulo.rotular(Features.construir(silver[silver["periodo"] == "B"], ficha))
    gold_x = pd.read_parquet(config.ARQUIVO_FEATURES, columns=["fluxo_id", "t"])
    assert len(rotulado) == len(gold_x), f"o motor tem {len(rotulado)} medições no Período B e o Gold {len(gold_x)}"

    gold = pd.read_parquet(config.ARQUIVO_ROTULADO)
    gold = gold[gold["bloco"] != config.BLOCO_TESTE].copy()  # o teste fica fechado: só treino e validação
    gold["t"] = (gold["t"] - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)
    juntas = gold.merge(rotulado, on=["fluxo_id", "t"], suffixes=("_gold", "_motor"), how="left", validate="one_to_one")
    assert juntas["regra_motor"].notna().all(), "há medição de treino ou validação do Gold que o motor não tem"
    for coluna in COLUNAS_NUMERICAS:
        assert _iguais(juntas[f"{coluna}_gold"], juntas[f"{coluna}_motor"]), f"X/Y: a coluna {coluna} difere do Gold"
    for coluna in COLUNAS_TEXTO:
        gold_c, motor_c = juntas[f"{coluna}_gold"], juntas[f"{coluna}_motor"]
        assert ((gold_c == motor_c) | (gold_c.isna() & motor_c.isna())).all(), f"X/Y: a coluna {coluna} difere do Gold"

    # --- O modelo dá a mesma previsão no X recalculado e no X do Gold ----------------------------------------
    modelo = ModeloExportado.ler().modelo
    colunas = DadosModelo.colunas_ajustadas()
    do_gold = modelo.predict(juntas[[f"{c}_gold" for c in colunas]].set_axis(colunas, axis=1).astype("float64"))
    do_motor = modelo.predict(juntas[[f"{c}_motor" for c in colunas]].set_axis(colunas, axis=1).astype("float64"))
    assert (do_gold == do_motor).all(), "a Random Forest prevê diferente no X do motor e no X do Gold"

    print(
        f"Motor × Gold: {len(ficha)} fichas, {len(juntas)} medições de treino e validação e {len(COLUNAS_NUMERICAS)} colunas "
        f"iguais (tolerância {parametros.TOLERANCIA:g}); status_atual e status_futuro iguais; "
        f"a Random Forest prevê o mesmo em {len(juntas)} medições."
    )


def leitor_contra_o_silver(cliente: ClienteAtlas) -> None:
    """Os resultados da API de um fluxo do treino, numa janela com timeout e perda parcial, viram as linhas do Silver."""
    _exigir_arquivos(config.ARQUIVO_SILVER)
    silver = pd.read_parquet(config.ARQUIVO_SILVER, columns=["fluxo_id", "msm_id", "prb_id", "t", "rtt", "jitter", "perda_pct", "timeout_atual"])
    silver["t"] = (silver["t"] - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)
    # A medição escolhida: a primeira com perda parcial (0 < perda < 100) e, em outro fluxo, a primeira com timeout. Assim a
    # janela cobre o RTT médio de 1 a 2 pings, o jitter nulo e o `timeout_atual` = 1, que um fluxo sem perda não exerce.
    parcial = silver[(silver["perda_pct"] > 0) & (silver["perda_pct"] < 100)].sort_values("t")
    total = silver[silver["timeout_atual"] == 1].sort_values("t")
    escolhidas = [linha for linha in (parcial.iloc[0] if len(parcial) else None, total.iloc[0] if len(total) else None) if linha is not None]
    assert escolhidas, "o Silver não tem nenhuma medição com perda para exercitar o leitor"

    for linha in escolhidas:
        # A janela é cortada no primeiro e no último instante do Silver: antes e depois deles a tabela de origem não tem o fluxo.
        inicio = max(int(linha["t"]) - parametros.FOLGA_DA_JANELA_S, int(silver["t"].min()))
        fim = min(int(linha["t"]) + parametros.FOLGA_DA_JANELA_S, int(silver["t"].max()))
        lidos = [ler_resultado(r) for r in cliente.resultados(int(linha["msm_id"]), [int(linha["prb_id"])], inicio, fim)]
        api = pd.DataFrame([r for r in lidos if r is not None])
        do_silver = silver[(silver["fluxo_id"] == linha["fluxo_id"]) & silver["t"].between(inicio, fim)]
        assert set(api["t"]) == set(do_silver["t"]), (
            f"{linha['fluxo_id']}: a API e o Silver têm instantes diferentes na janela ({len(api)} × {len(do_silver)})"
        )
        juntas = api.merge(do_silver, on="t", suffixes=("_api", "_silver"), validate="one_to_one")
        for coluna in ("rtt", "jitter", "perda_pct", "timeout_atual"):
            igual = _iguais(
                juntas[f"{coluna}_api"], juntas[f"{coluna}_silver"], parametros.TOLERANCIA_LEITOR_REL, parametros.TOLERANCIA_LEITOR_ABS_MS
            )
            assert igual, f"{linha['fluxo_id']}: {coluna} da API difere do Silver"
        print(
            f"Leitor × Silver: {linha['fluxo_id']}, {len(juntas)} medições em torno de t={int(linha['t'])} "
            f"(perda {linha['perda_pct']:.0f} %, timeout_atual {int(linha['timeout_atual'])}): rtt, jitter, perda e timeout iguais (RTT do Silver em float32)."
        )
