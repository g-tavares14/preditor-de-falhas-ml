"""Monta o documento do replay: uma linha por medição da validação, com a previsão da árvore (SPEC-visualizacao.md).

Entrada: `dataset_rotulado_B.parquet` do Gold e a árvore oficial já treinada. Nada do X nem do Y é recalculado aqui:
o JSON só repete o que o Gold já tem e acrescenta a classe que a árvore prevê para cada medição.
"""

import json
from datetime import datetime, timezone

import pandas as pd

from preditor import config
from preditor.modelo.arvore import Arvore
from preditor.modelo.dados import BLOCOS_USADOS, DadosModelo
from preditor.modelo.regras import Regra, Regras
from preditor.visualizacao.rotas import Rotas

# `t` do Gold é um timestamp em UTC (o Spark roda em UTC, ver `spark.py`) que o pandas devolve sem fuso.
# Segundos desde esta data = o `t` do JSON, um inteiro que o navegador entende sem converter fuso.
EPOCA = pd.Timestamp("1970-01-01")
FORMATO_INSTANTE = "%Y-%m-%dT%H:%M:%SZ"


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
    def prever(bloco: pd.DataFrame, arvore: Arvore) -> pd.Series:
        """Classe prevista pela árvore oficial para TODAS as medições do bloco (as não conferíveis também)."""
        # Mesmas 8 colunas e mesmo tipo que `DadosModelo` entrega à árvore; NaN continua NaN (RFC §8.3).
        return arvore.prever(bloco[config.COLUNAS_ARVORE].astype("float64"))

    @staticmethod
    def folhas(bloco: pd.DataFrame, arvore: Arvore) -> pd.Series:
        """Número da folha (nó de `tree_`) que decide a previsão de cada medição do bloco: `apply` da árvore oficial."""
        X = bloco[config.COLUNAS_ARVORE].astype("float64")  # o mesmo X de `prever`
        return pd.Series(arvore.modelo.apply(X), index=bloco.index)

    @staticmethod
    def regras_das_folhas(arvore: Arvore, dados: DadosModelo) -> dict[int, Regra]:
        """Uma `Regra` para CADA folha da árvore oficial (`Regras.ler` devolve só as 3 mais cheias).

        Mesmo caminho real raiz → folha de `tree_`, mesma fusão e mesmo texto de `modelo/regras.py`: nada é escrito à
        mão. Só o conjunto de folhas muda (todas, e não as de maior N), porque a página explica qualquer previsão.
        """
        modelo = arvore.modelo
        X, y = dados.X[config.BLOCO_TREINO], dados.y[config.BLOCO_TREINO]
        folha_de_cada_linha = modelo.apply(X)
        # Mesma definição de `Regras.ler`: a regra só precisa dizer para onde vai o ausente nas colunas que o têm.
        com_ausente = {
            coluna for coluna in config.COLUNAS_ARVORE if any(dados.X[bloco][coluna].isna().any() for bloco in BLOCOS_USADOS)
        }
        regras = {}
        for folha, caminho in Regras._caminhos(modelo, com_ausente).items():
            classe = str(modelo.classes_[modelo.tree_.value[folha].argmax()])
            linhas = folha_de_cada_linha == folha
            regras[folha] = Regra(
                folha=int(folha),
                classe=classe,
                n_treino=int(linhas.sum()),
                pureza=float((y[linhas] == classe).mean()),
                condicoes=tuple(caminho),
                fundidas=Regras.fundir(caminho),
            )
        return regras

    @staticmethod
    def montar(bloco: pd.DataFrame, previsto: pd.Series, folhas: pd.Series, regras: dict[int, Regra]) -> dict:
        """O documento completo, pronto para `json.dumps`."""
        # Ordem de tempo; `fluxo_id` desempata medições do mesmo segundo, para a saída não depender da leitura.
        ordenado = bloco.sort_values(["t", "fluxo_id"], kind="stable")
        fluxos = ExportadorReplay._montar_fluxos(ordenado)
        posicao_do_fluxo = {fluxo["id"]: posicao for posicao, fluxo in enumerate(fluxos)}
        medicoes = ExportadorReplay._montar_medicoes(ordenado, previsto, folhas, posicao_do_fluxo)
        return {
            "meta": {
                "bloco": config.BLOCO_REPLAY,
                "inicio": ExportadorReplay.formatar_instante(medicoes[0]["t"]),
                "fim": ExportadorReplay.formatar_instante(medicoes[-1]["t"]),
                "classes": list(config.CLASSES),
                "aviso": config.AVISO_ROTA,
            },
            # Os nomes das 8 colunas de `x` (a página não tem nome nenhum escrito) e a regra em português de cada folha.
            "colunas": list(config.COLUNAS_ARVORE),
            "regras": {str(folha): regra.texto() for folha, regra in sorted(regras.items())},
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
    def _montar_medicoes(
        ordenado: pd.DataFrame, previsto: pd.Series, folhas: pd.Series, posicao_do_fluxo: dict[str, int]
    ) -> list[dict]:
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
                    "folha": int(folhas.loc[indice]),
                    # O futuro só vai para o JSON quando conta no placar. Nas 3 últimas medições de cada fluxo
                    # ele é o `status_atual` de uma medição do bloco seguinte (o teste): fica de fora.
                    "futuro": linha[config.ALVO] if conferivel else None,
                    "conferivel": conferivel,
                    # Instante (segundos UTC) em que o futuro acontece e a previsão pode ser conferida; nulo nas demais.
                    "t_futuro": int(futuros.loc[indice]) if conferivel else None,
                    # As 8 colunas que a árvore viu, na ordem de `colunas`; ausente = `null` (RFC §8.3: nunca imputado).
                    "x": [ExportadorReplay._arredondar(linha[coluna], config.CASAS_X_REPLAY) for coluna in config.COLUNAS_ARVORE],
                }
            )
        return medicoes

    @staticmethod
    def formatar_instante(segundos: int) -> str:
        return datetime.fromtimestamp(segundos, tz=timezone.utc).strftime(FORMATO_INSTANTE)
