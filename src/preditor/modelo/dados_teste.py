"""Leitura de UM bloco do dataset rotulado, para o teste único (SPEC-teste-final.md, "Regras fixadas").

`DadosModelo` lê o Gold inteiro e guarda só treino e validação. Este módulo lê um bloco por vez, com o filtro do próprio
Parquet, e só o `execucao_teste.py` o importa (conferido por `grep`). O bloco `teste` só se conta (N): carregar as linhas
dele é a abertura, liberada por argumento e recusada antes de qualquer leitura.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from preditor import config
from preditor.modelo.dados import DadosModelo


@dataclass(frozen=True)
class BlocoLido:
    """Um bloco lido de uma vez, com as mesmas regras de `DadosModelo` (folga, futuro nulo, ausentes intactos)."""

    bloco: str
    X: pd.DataFrame  # as 10 colunas do modelo (`DadosModelo.colunas_ajustadas`), float64, com NaN onde o Gold tem NaN
    y: pd.Series  # `status_futuro`, o alvo; mesmas linhas do X
    status_atual: pd.Series  # só a persistência usa; é proibido no X
    localizacao: pd.DataFrame  # `fluxo_id`, `t`, `rtt` e a mediana do baseline do fluxo: só localizam a linha
    mediana_das_medianas: float  # a mesma de `DadosModelo` (os fluxos com baseline suficiente)


class DadosTeste:
    def __init__(self, bloco: str) -> None:
        assert bloco in (config.BLOCO_TREINO, config.BLOCO_VALIDACAO, config.BLOCO_TESTE), (
            f"bloco desconhecido: {bloco!r}"
        )
        self.bloco = bloco

    def contar(self) -> int:
        """N do bloco de teste: as linhas com `status_futuro` (no teste não há folga). Lê só `bloco` e `status_futuro`."""
        assert self.bloco == config.BLOCO_TESTE, "contar() é só do teste; treino e validação usam carregar()"
        lido = _ler_bloco(self.bloco, colunas=["bloco", config.ALVO])
        return int(lido[config.ALVO].notna().sum())

    def carregar(self, *, liberar_teste: bool = False) -> BlocoLido:
        """Lê o bloco e aplica as regras de `DadosModelo`: folga, futuro nulo e X com as 10 colunas."""
        # A barreira do teste vem ANTES de qualquer leitura: sem a liberação, o arquivo nem é aberto.
        assert self.bloco != config.BLOCO_TESTE or liberar_teste, (
            "o bloco teste só é lido na abertura (liberar_teste=True); até lá, use contar()"
        )
        colunas = DadosModelo.colunas_ajustadas()
        lido = _ler_bloco(self.bloco)
        faltando = [coluna for coluna in colunas if coluna not in lido.columns]
        if faltando:
            # Gold antigo, sem o histórico do z: a mesma mensagem de `DadosModelo._ler`.
            raise SystemExit(
                f"{config.ARQUIVO_ROTULADO} não tem as colunas {faltando}.\n"
                "Rode antes: uv run python -m preditor gold"
            )

        # A folga é a de `DadosModelo` (a mesma função). Por (fluxo, bloco), ela não depende dos outros blocos.
        marcado = DadosModelo._marcar_folga(lido)
        mantida = marcado[config.ALVO].notna() & ~marcado["folga"]
        mantidas = marcado[mantida]

        # Valores ausentes ficam ausentes (RFC §8.3): só `astype`, nenhum `fillna`.
        X = mantidas[colunas].astype("float64")
        mediana_por_fluxo, mediana_das_medianas = _medianas()
        localizacao = mantidas[config.COLUNAS_LOCALIZACAO].copy()
        localizacao[config.COLUNA_MEDIANA_FLUXO] = localizacao["fluxo_id"].map(mediana_por_fluxo)

        resultado = BlocoLido(
            bloco=self.bloco,
            X=X,
            y=mantidas[config.ALVO],
            status_atual=mantidas["status_atual"],
            localizacao=localizacao,
            mediana_das_medianas=mediana_das_medianas,
        )
        self._verificar(resultado, mantidas, mediana_por_fluxo)
        return resultado

    def _verificar(self, bloco: BlocoLido, mantidas: pd.DataFrame, mediana_por_fluxo: pd.Series) -> None:
        """Checagens do bloco lido: colunas, tipos, ausentes intactos, classes e mediana de cada linha."""
        X, y, loc = bloco.X, bloco.y, bloco.localizacao
        assert list(X.columns) == DadosModelo.colunas_ajustadas(), f"{self.bloco}: X com colunas diferentes: {list(X.columns)}"
        proibidas = set(X.columns) & set(config.COLUNAS_PROIBIDAS)
        assert not proibidas, f"{self.bloco}: colunas proibidas no X: {sorted(proibidas)}"
        assert (X.dtypes == "float64").all(), f"{self.bloco}: X precisa ser float64 (com NaN)"
        assert X.index.equals(y.index) and X.index.equals(loc.index), f"{self.bloco}: X, y e localização com linhas diferentes"
        assert y.notna().all(), f"{self.bloco}: sobrou status_futuro nulo"
        assert set(y) <= set(config.CLASSES), f"{self.bloco}: classe fora de {config.CLASSES}: {sorted(set(y))}"
        if self.bloco != config.BLOCO_TESTE:
            # Treino e validação precisam das 3 classes; o teste não é medido aqui, então não entra nesta conta.
            assert set(y) == set(config.CLASSES), f"{self.bloco}: falta classe: {sorted(set(y))}"
        # Ausente do X é o ausente do Gold, linha a linha (nada foi preenchido).
        assert (X.isna().to_numpy() == mantidas[X.columns].isna().to_numpy()).all(), f"{self.bloco}: ausentes alterados"

        # Toda linha tem a mediana do próprio fluxo; a mediana das medianas é a de DadosModelo, por outro caminho (numpy).
        assert loc[config.COLUNA_MEDIANA_FLUXO].notna().all(), f"{self.bloco}: linha sem mediana de baseline"
        assert np.isclose(bloco.mediana_das_medianas, np.median(mediana_por_fluxo.to_numpy()), rtol=0,
                          atol=config.TOLERANCIA_METRICA), f"{self.bloco}: a mediana das medianas não bate"


def _ler_bloco(bloco: str, colunas: list[str] | None = None) -> pd.DataFrame:
    """Lê do Gold só as linhas do bloco (e só as colunas pedidas). O filtro é do próprio Parquet: as outras linhas
    nem chegam à memória."""
    if not config.ARQUIVO_ROTULADO.exists():
        # Mesma mensagem de `DadosModelo._ler`: a camada anterior é a que falta.
        raise SystemExit(
            f"Não encontrei {config.ARQUIVO_ROTULADO}.\n"
            "Rode antes: uv run python -m preditor gold"
        )
    return pd.read_parquet(config.ARQUIVO_ROTULADO, columns=colunas, filters=[("bloco", "==", bloco)])


def _medianas() -> tuple[pd.Series, float]:
    """Mediana do baseline de cada fluxo com baseline suficiente, e a mediana delas (como `DadosModelo._juntar_medianas`)."""
    if not config.ARQUIVO_BASELINE.exists():
        raise SystemExit(
            f"Não encontrei {config.ARQUIVO_BASELINE}.\n"
            "Rode antes: uv run python -m preditor gold"
        )
    baseline = pd.read_parquet(config.ARQUIVO_BASELINE)
    com_baseline = baseline.loc[~baseline["baseline_insuficiente"]]
    mediana_por_fluxo = com_baseline.set_index("fluxo_id")["mediana"]
    # 81 fluxos no baseline, 2 com `baseline_insuficiente` (config.py): 79 entram. O número vem do dataset, não é escolhido.
    assert len(mediana_por_fluxo) == config.FLUXOS_BASELINE - config.FLUXOS_INSUFICIENTES, (
        f"fluxos com baseline suficiente: {len(mediana_por_fluxo)}"
    )
    return mediana_por_fluxo, float(mediana_por_fluxo.median())
