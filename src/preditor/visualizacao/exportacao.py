"""Monta o documento do replay: uma linha por medição da validação, com a previsão da Random Forest (SPEC-replay-floresta.md).

Entrada: `dataset_rotulado_B.parquet` do Gold e o `modelo_final.joblib` exportado. Nada do X nem do Y é recalculado aqui:
o JSON só repete o que o Gold já tem e acrescenta a classe que a floresta prevê para cada medição.
"""

import json
from datetime import datetime, timezone

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from preditor import config
from preditor.modelo.dados import DadosModelo
from preditor.visualizacao.modelo_exportado import ModeloExportado
from preditor.visualizacao.rotas import Rotas

# `t` do Gold é um timestamp em UTC (o Spark roda em UTC, ver `spark.py`) que o pandas devolve sem fuso.
# Segundos desde esta data = o `t` do JSON, um inteiro que o navegador entende sem converter fuso.
EPOCA = pd.Timestamp("1970-01-01")
FORMATO_INSTANTE = "%Y-%m-%dT%H:%M:%SZ"
# O nome que a página mostra ("Random Forest, 100 árvores"). O código do projeto (`config.MODELO_FLORESTA`) não serve para
# quem não é da área. Fica aqui e não em config.py: o `config.py` faz parte do carimbo do teste (`CODIGO_DE_MEDICAO`).
NOME_DA_FLORESTA = "Random Forest"


class ExportadorReplay:
    @staticmethod
    def ler_validacao() -> pd.DataFrame:
        """Lê o Gold e devolve só o bloco exibido, com a marca `conferivel` em cada medição."""
        # `_ler` termina com "Rode antes: uv run python -m preditor gold" se o Gold não está no disco.
        lido = DadosModelo._ler()
        # O teste sai logo na leitura: nada do que vem depois o enxerga (e a execução confere isso no fim).
        bloco = lido[lido["bloco"] == config.BLOCO_REPLAY].copy()
        return ExportadorReplay._marcar_conferiveis(bloco)

    @staticmethod
    def ler_medianas() -> pd.Series:
        """`fluxo_id` → mediana real do RTT no baseline (ms); `NaN` nos fluxos com `baseline_insuficiente`."""
        if not config.ARQUIVO_BASELINE.exists():
            raise SystemExit(f"Não encontrei {config.ARQUIVO_BASELINE}.\nRode antes: uv run python -m preditor gold")
        return pd.read_parquet(config.ARQUIVO_BASELINE, columns=["fluxo_id", "mediana"]).set_index("fluxo_id")["mediana"]

    @staticmethod
    def _marcar_conferiveis(bloco: pd.DataFrame) -> pd.DataFrame:
        """`conferivel` = tem `status_futuro` e está fora da folga: as linhas que o placar conta."""
        # A folga é a MESMA regra de `DadosModelo` (as 3 últimas medições de cada fluxo no bloco, RFC §9), marcada
        # antes de olhar o futuro nulo. Ela devolve as linhas ordenadas por `t`; o índice do Parquet é mantido.
        com_folga = DadosModelo._marcar_folga(bloco)
        com_folga["conferivel"] = com_folga[config.ALVO].notna() & ~com_folga["folga"]
        com_folga["t_futuro"] = ExportadorReplay._instante_do_futuro(com_folga)
        return com_folga

    @staticmethod
    def _instante_do_futuro(bloco: pd.DataFrame) -> pd.Series:
        """`t` da 3ª medição seguinte do mesmo fluxo (de onde vem o `status_futuro`); nulo nas não conferíveis."""
        # Mesma definição do Gold (`lead` de PASSOS_FUTURO linhas no fluxo, em ordem de tempo), feita aqui com `shift`.
        # Só as conferíveis ficam com valor: nelas a 3ª seguinte está no próprio bloco (folga) e a 10 a 14 min (futuro
        # não nulo); nas demais o futuro não é "12 min depois" e o placar não as conta.
        por_fluxo = bloco.sort_values(["fluxo_id", "t"], kind="stable")
        t_depois = por_fluxo.groupby("fluxo_id")["t"].shift(-config.PASSOS_FUTURO)
        return t_depois.where(bloco["conferivel"]).reindex(bloco.index)

    @staticmethod
    def x(bloco: pd.DataFrame) -> pd.DataFrame:
        """As 10 colunas que a floresta viu, em float64 e na ordem do `.joblib`; NaN continua NaN (RFC §8.3)."""
        return bloco[DadosModelo.colunas_ajustadas()].astype("float64")

    @staticmethod
    def prever(bloco: pd.DataFrame, modelo: RandomForestClassifier) -> pd.Series:
        """Classe prevista pela Random Forest para TODAS as medições do bloco (as não conferíveis também)."""
        return pd.Series(modelo.predict(ExportadorReplay.x(bloco)), index=bloco.index)

    @staticmethod
    def bloco_modelo(exportado: ModeloExportado) -> dict:
        """O que a página mostra do modelo e o que o JSON prova sobre ele: nome, família, árvores, parâmetros, SHA-256, colunas."""
        modelo = exportado.modelo
        return {
            "nome": NOME_DA_FLORESTA,
            "familia": config.MODELO_FLORESTA,
            "arvores": int(modelo.n_estimators),
            "parametros": exportado.parametros,
            "sha256": exportado.sha256,
            "colunas": [str(coluna) for coluna in modelo.feature_names_in_],
        }

    @staticmethod
    def montar(bloco: pd.DataFrame, previsto: pd.Series, modelo: dict) -> dict:
        """O documento completo, pronto para `json.dumps`."""
        # Ordem de tempo; `fluxo_id` desempata medições do mesmo segundo, para a saída não depender da leitura.
        ordenado = bloco.sort_values(["t", "fluxo_id"], kind="stable")
        fluxos = ExportadorReplay._montar_fluxos(ordenado)
        posicao_do_fluxo = {fluxo["id"]: posicao for posicao, fluxo in enumerate(fluxos)}
        medicoes = ExportadorReplay._montar_medicoes(ordenado, previsto, posicao_do_fluxo)
        return {
            "meta": {
                "bloco": config.BLOCO_REPLAY,
                "inicio": ExportadorReplay.formatar_instante(medicoes[0]["t"]),
                "fim": ExportadorReplay.formatar_instante(medicoes[-1]["t"]),
                "classes": list(config.CLASSES),
                "aviso": config.AVISO_ROTA,
            },
            # A floresta que prevê cada medição: a página lê `nome` e `arvores`; o resto serve para conferir o arquivo.
            "modelo": modelo,
            "fluxos": fluxos,
            "medicoes": medicoes,
        }

    @staticmethod
    def texto(documento: dict) -> str:
        """O JSON como texto: compacto (são ~14 mil medições), sem NaN (inválido em JSON) e sempre igual para a mesma entrada."""
        return json.dumps(documento, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"

    @staticmethod
    def _montar_fluxos(ordenado: pd.DataFrame) -> list[dict]:
        """Um fluxo por `fluxo_id`, em ordem alfabética, com região, país e a rota simulada em trechos."""
        # Cada fluxo tem um único país e uma única região (conferido na execução, que lê o JSON de volta).
        por_fluxo = ordenado.groupby("fluxo_id")[["destination_region", "destination_country"]].first()
        # Lê `sondas.csv` uma vez; sem ele, termina pedindo o script que o gera.
        rotas = Rotas()
        # A rota só pode ser fisicamente possível para a mediana real do fluxo (ver `Rotas.rotas_possiveis`).
        medianas = ExportadorReplay.ler_medianas()
        fluxos = []
        for fluxo_id, linha in por_fluxo.iterrows():
            rota = rotas.montar(fluxo_id, linha["destination_country"], medianas.loc[fluxo_id])
            fluxos.append(
                {
                    "id": fluxo_id,
                    "regiao": linha["destination_region"],
                    "pais": linha["destination_country"],
                    "opcao": rota["opcao"],
                    "km": rota["km"],
                    "rtt_minimo_ms": rota["rtt_minimo_ms"],
                    # Mediana real do baseline, ao lado do mínimo teórico no cartão; nula se o baseline é insuficiente.
                    "mediana_ms": ExportadorReplay._arredondar(medianas.loc[fluxo_id], config.CASAS_RTT_REPLAY),
                    "trechos": rota["trechos"],
                }
            )
        return fluxos

    @staticmethod
    def _arredondar(valor: float, casas: int) -> float | int | None:
        """`NaN` vira `None` (ausente continua ausente, nunca 0); inteiro exato vira `int` (3.0 → 3), que ocupa menos."""
        if pd.isna(valor):
            return None
        arredondado = round(float(valor), casas)
        return int(arredondado) if arredondado.is_integer() else arredondado

    @staticmethod
    def _montar_medicoes(ordenado: pd.DataFrame, previsto: pd.Series, posicao_do_fluxo: dict[str, int]) -> list[dict]:
        # Segundos desde 1970 (inteiros): a divisão de timestamp por 1 s não depende da resolução (ns ou µs) do pandas.
        segundos = (ordenado["t"] - EPOCA) // pd.Timedelta(seconds=1)
        previsto_na_ordem = previsto.loc[ordenado.index]
        # Mesma conversão para o `t_futuro`: o `NaT` das não conferíveis vira `NaN` e nunca é lido.
        futuros = (ordenado["t_futuro"] - EPOCA) // pd.Timedelta(seconds=1)

        medicoes = []
        for indice, linha in ordenado.iterrows():
            conferivel = bool(linha["conferivel"])
            medicoes.append(
                {
                    "f": posicao_do_fluxo[linha["fluxo_id"]],
                    "t": int(segundos.loc[indice]),
                    # Sem resposta em nenhum ping, o RTT é nulo (e `timeout` vale 1): vira `null` no JSON.
                    "rtt": None if pd.isna(linha["rtt"]) else round(float(linha["rtt"]), config.CASAS_RTT_REPLAY),
                    "timeout": int(linha["timeout_atual"]),
                    "atual": linha["status_atual"],
                    "previsto": previsto_na_ordem.loc[indice],
                    # O futuro só vai para o JSON quando conta no placar. Nas 3 últimas medições de cada fluxo
                    # ele é o `status_atual` de uma medição do bloco seguinte (o teste): fica de fora.
                    "futuro": linha[config.ALVO] if conferivel else None,
                    "conferivel": conferivel,
                    # Instante (segundos UTC) em que o futuro acontece e a previsão pode ser conferida; nulo nas demais.
                    "t_futuro": int(futuros.loc[indice]) if conferivel else None,
                }
            )
        return medicoes

    @staticmethod
    def formatar_instante(segundos: int) -> str:
        return datetime.fromtimestamp(segundos, tz=timezone.utc).strftime(FORMATO_INSTANTE)
