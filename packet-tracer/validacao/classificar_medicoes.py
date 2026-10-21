from pathlib import Path
import numpy as np
import pandas as pd

pasta_projeto = Path(__file__).resolve().parent
arquivo = pasta_projeto / "data" / "medicoes_completas..csv.xlsx"
dados = pd.read_excel(arquivo, sheet_name="medicoes_pt.csv.")

colunas_necessarias = ["periodo", "fluxo_id", "timestamp", "latencia_ms", "jitter_ms", "rcvd", "perda_pct", "timeout_atual", "cenario"]
faltantes = [c for c in colunas_necessarias if c not in dados.columns]
if faltantes:
    raise ValueError(f"Colunas ausentes: {faltantes}")

periodo_a = dados[dados["periodo"] == "A"].copy()
periodo_b = dados[dados["periodo"] == "B"].copy()
if periodo_a.empty or periodo_b.empty:
    raise ValueError("Os períodos A e B devem conter medições.")

for coluna in ["latencia_ms", "jitter_ms", "rcvd", "perda_pct", "timeout_atual"]:
    periodo_a[coluna] = pd.to_numeric(periodo_a[coluna], errors="coerce")
    periodo_b[coluna] = pd.to_numeric(periodo_b[coluna], errors="coerce")

periodo_b["timestamp"] = pd.to_datetime(periodo_b["timestamp"], errors="raise", utc=True)
periodo_b = periodo_b.sort_values(["fluxo_id", "timestamp"], kind="stable").copy()
if periodo_b[["rcvd", "perda_pct", "timeout_atual"]].isna().any().any():
    raise ValueError("Valores inválidos de recebimento, perda ou timeout no Período B.")

baseline_a = periodo_a[(periodo_a["rcvd"] > 0) & periodo_a["latencia_ms"].notna()].copy()
if baseline_a.empty:
    raise ValueError("Não há RTT válido no Período A.")
medianas = baseline_a.groupby("fluxo_id")["latencia_ms"].median()
baseline_a["desvio"] = (baseline_a["latencia_ms"] - baseline_a["fluxo_id"].map(medianas)).abs()
mads = baseline_a.groupby("fluxo_id")["desvio"].median()
iqrs = baseline_a.groupby("fluxo_id")["latencia_ms"].agg(lambda v: v.quantile(.75) - v.quantile(.25))
jitter_tipico = baseline_a.groupby("fluxo_id")["jitter_ms"].median()
for coluna, serie in [("mediana", medianas), ("mad", mads), ("iqr", iqrs), ("jitter_tipico", jitter_tipico)]:
    periodo_b[coluna] = periodo_b["fluxo_id"].map(serie)
if periodo_b[["mediana", "mad", "iqr"]].isna().any().any() or (periodo_b["mediana"] <= 0).any():
    raise ValueError("Fluxo sem baseline válido ou com mediana não positiva.")

periodo_b.loc[periodo_b["rcvd"] == 0, ["latencia_ms", "jitter_ms"]] = np.nan
desvio = periodo_b["latencia_ms"] - periodo_b["mediana"]
periodo_b["aumento_pct"] = 100 * desvio / periodo_b["mediana"]
escala = np.where(periodo_b["mad"] > 0, 1.4826 * periodo_b["mad"], np.maximum(periodo_b["iqr"] / 1.349, 1.0))
periodo_b["z_robusto"] = desvio / escala
periodo_b.loc[(periodo_b["mad"] == 0) & (desvio == 0), "z_robusto"] = 0.0
periodo_b["jitter_relativo"] = np.where(
    periodo_b["jitter_ms"].notna() & periodo_b["jitter_tipico"].notna(),
    np.where(periodo_b["jitter_tipico"] > 0,
             periodo_b["jitter_ms"] / periodo_b["jitter_tipico"].replace(0, np.nan),
             np.where(periodo_b["jitter_ms"] == 0, 1.0, 3.0)),
    np.nan,
)

periodo_b["falha_perda"] = periodo_b["perda_pct"] >= 10
periodo_b["n5_timeout"] = periodo_b.groupby("fluxo_id")["timeout_atual"].transform(lambda v: v.rolling(5, min_periods=1).sum())
periodo_b["falha_timeout"] = periodo_b["n5_timeout"] >= 3
periodo_b["falha_z"] = (periodo_b["z_robusto"] >= 3.5) & (periodo_b["aumento_pct"] >= 30)
periodo_b["aumento80"] = (periodo_b["aumento_pct"] > 80).astype(int)
periodo_b["n5_aumento80"] = periodo_b.groupby("fluxo_id")["aumento80"].transform(lambda v: v.rolling(5, min_periods=1).sum())
periodo_b["falha_aumento80"] = periodo_b["n5_aumento80"] >= 2
periodo_b["moderado"] = (periodo_b["z_robusto"].between(2, 3.5, inclusive="left") | periodo_b["aumento_pct"].between(30, 80) | (periodo_b["jitter_relativo"] >= 3)).astype(int)
periodo_b["n5_moderado"] = periodo_b.groupby("fluxo_id")["moderado"].transform(lambda v: v.rolling(5, min_periods=1).sum())
condicoes = [periodo_b["falha_perda"], periodo_b["falha_timeout"], periodo_b["falha_z"], periodo_b["falha_aumento80"], (periodo_b["moderado"] == 1) & (periodo_b["n5_moderado"] >= 2)]
periodo_b["regra"] = np.select(condicoes, [1, 2, 3, 4, 5], default=6)
periodo_b["status_atual"] = np.select([periodo_b["regra"] <= 4, periodo_b["regra"] == 5], ["FALHA", "RISCO"], default="OK")
saida = pasta_projeto / "data" / "classificacao_preliminar.csv"
periodo_b.to_csv(saida, sep=";", index=False, encoding="utf-8-sig")
print("Total de medições:", len(dados))
print("Período A:", len(periodo_a))
print("Período B:", len(periodo_b))
print("\nClassificação por cenário:")
print(periodo_b.groupby(["cenario", "status_atual"]).size())
print("\nTotal por classificação:")
print(periodo_b["status_atual"].value_counts())
print("\nQuantidade por regra:")
print(periodo_b["regra"].value_counts().sort_index())
print("\nArquivo salvo em:", saida)
print("\nATENÇÃO: baseline experimental reduzido; o original exige 1.500 RTT válidos por fluxo.")
