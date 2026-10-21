from pathlib import Path
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

pasta_projeto = Path(__file__).resolve().parent
df = pd.read_csv(pasta_projeto / "data" / "classificacao_preliminar.csv", sep=";")
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="raise", utc=True)
df = df.sort_values(["timestamp", "fluxo_id"], kind="stable").reset_index(drop=True)
colunas = ["z_robusto", "aumento_pct", "jitter_relativo", "perda_pct", "timeout_atual", "n5_timeout", "n5_aumento80", "n5_moderado"]
faltantes = [c for c in colunas if c not in df.columns]
if faltantes:
    raise ValueError(f"Features ausentes: {faltantes}")
X = df[colunas].fillna(0)
y = df["status_atual"]
total = len(df)
fim_treino = int(total * 0.50)
fim_validacao = int(total * 0.70)
if not 0 < fim_treino < fim_validacao < total:
    raise ValueError("Quantidade de medições insuficiente para a divisão temporal.")
partes = {
    "Treinamento": df.iloc[:fim_treino],
    "Validação": df.iloc[fim_treino:fim_validacao],
    "Teste": df.iloc[fim_validacao:],
}
print("Total de medições:", total)
for nome, parte in partes.items():
    print(f"\n{nome}: {len(parte)} medições")
    print("Início:", parte["timestamp"].min(), "Fim:", parte["timestamp"].max())
    print("Cenários:\n", parte["cenario"].value_counts())
    print("Classes:\n", parte["status_atual"].value_counts())
classes = ["OK", "RISCO", "FALHA"]
ausentes = [c for c in classes if c not in partes["Treinamento"]["status_atual"].unique()]
if ausentes:
    print("\nATENÇÃO: classes ausentes no treinamento:", ausentes)
for i in [fim_treino, fim_validacao]:
    if df.loc[i - 1, "timestamp"] == df.loc[i, "timestamp"]:
        print("ATENÇÃO: divisão atravessa timestamps iguais na posição", i)
modelo = DecisionTreeClassifier(max_depth=4, random_state=42)
modelo.fit(X.iloc[:fim_treino], y.iloc[:fim_treino])
print("\nClasses aprendidas pelo modelo:", modelo.classes_)
for nome, inicio, fim in [("Validação", fim_treino, fim_validacao), ("Teste", fim_validacao, total)]:
    real = y.iloc[inicio:fim]
    previsto = modelo.predict(X.iloc[inicio:fim])
    print(f"\nResultado da {nome}:")
    print("Acurácia:", accuracy_score(real, previsto))
    print(classification_report(real, previsto, labels=classes, zero_division=0))
    print("Matriz de confusão:\n", confusion_matrix(real, previsto, labels=classes))
print("\nAVISO: avalia status_atual, não previsão de status_futuro.")
