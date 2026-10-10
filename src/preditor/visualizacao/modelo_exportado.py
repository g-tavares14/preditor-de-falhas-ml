"""Lê o `modelo_final.joblib` exportado para o replay, com as mesmas conferências do `teste` (SPEC-replay-floresta.md).

O `teste` tem a sua leitura em `modelo/execucao_teste.py`, e esse arquivo não pode mudar (o carimbo do ensaio guarda o hash
dele). Por isso aqui há uma cópia das duas conferências que importam: o SHA-256 contra o LEIA-ME, feito ANTES de abrir o
arquivo (um `.joblib` é um pickle, e abrir um pickle executa código), e o pacote contra o `escolha.json`.
`execucao_teste.py` não é importado daqui: ele carrega o bloco de teste.
"""

import hashlib
import json
import re
from dataclasses import dataclass

import joblib
from sklearn.ensemble import RandomForestClassifier

from preditor import config
from preditor.modelo.dados import DadosModelo


@dataclass(frozen=True)
class ModeloExportado:
    """A floresta exportada, já conferida: o objeto, o SHA-256 do arquivo e os parâmetros que o `escolha.json` descreve."""

    modelo: RandomForestClassifier
    sha256: str
    parametros: dict

    @staticmethod
    def ler() -> "ModeloExportado":
        """Confere o arquivo (SHA-256 e pacote) e só então o abre. Sem os arquivos, pede o `exportar`."""
        necessarios = (config.ARQUIVO_MODELO_FINAL, config.ARQUIVO_LEIA_ME, config.ARQUIVO_ESCOLHA)
        faltando = [str(arquivo) for arquivo in necessarios if not arquivo.exists()]
        if faltando:
            raise SystemExit(
                f"Não encontrei {', '.join(faltando)}.\n"
                "Rode antes: uv run python -m preditor exportar (que precisa do comparar antes)"
            )
        escolha = json.loads(config.ARQUIVO_ESCOLHA.read_text(encoding="utf-8"))
        sha = _sha256(config.ARQUIVO_MODELO_FINAL)
        _exigir_sha_do_leia_me(sha)  # antes de abrir: o .joblib é um pickle
        modelo = _conferir_pacote(joblib.load(config.ARQUIVO_MODELO_FINAL), escolha)
        return ModeloExportado(modelo=modelo, sha256=sha, parametros=escolha["parametros"])


def _exigir_sha_do_leia_me(sha: str) -> None:
    """O arquivo que vai ser aberto é o que a exportação gravou: o SHA-256 tem de bater com a tabela do LEIA-ME."""
    for linha in config.ARQUIVO_LEIA_ME.read_text(encoding="utf-8").splitlines():
        if linha.startswith(f"| `{config.ARQUIVO_MODELO_FINAL.name}`"):
            achado = re.search(r"`([0-9a-f]{64})`", linha)
            assert achado is not None, "a linha do modelo no LEIA-ME não tem um SHA-256"
            gravado = achado.group(1)
            if gravado != sha:
                raise SystemExit(
                    f"{config.ARQUIVO_MODELO_FINAL.name} mudou desde a exportação: SHA-256 {sha}, "
                    f"e o LEIA-ME tem {gravado}.\nNada foi lido. Refaça a exportação: uv run python -m preditor exportar"
                )
            return
    raise SystemExit(f"O LEIA-ME não tem a linha de {config.ARQUIVO_MODELO_FINAL.name}: não dá para conferir o SHA-256.")


def _conferir_pacote(pacote: dict, escolha: dict) -> RandomForestClassifier:
    """O pacote é o que a escolha descreve: família, parâmetros, as 10 colunas na ordem, sem rótulo extra."""
    assert pacote["formato"] == config.FORMATO_EXPORTADO, f"formato do pacote: {pacote['formato']}"
    assert pacote["familia"] == escolha["modelo"] == config.MODELO_FLORESTA, (
        f"família no pacote ({pacote['familia']}) ≠ escolha ({escolha['modelo']}) ≠ {config.MODELO_FLORESTA}"
    )
    assert pacote["parametros"] == escolha["parametros"], "parâmetros do pacote diferentes de escolha.json"
    assert pacote["colunas"] == DadosModelo.colunas_ajustadas(), f"colunas do pacote: {pacote['colunas']}"
    assert pacote["rotulos_do_modelo"] is None, "a floresta devolve o texto da classe; rótulos extras não cabem aqui"

    modelo = pacote["modelo"]
    assert isinstance(modelo, RandomForestClassifier), f"o modelo do pacote é {type(modelo).__name__}"
    parametros = escolha["parametros"]
    assert (modelo.n_estimators, modelo.max_depth, modelo.min_samples_leaf) == (
        parametros["n_estimators"], parametros["max_depth"], parametros["min_samples_leaf"]
    ), "hiperparâmetros do modelo carregado diferentes dos gravados"
    assert modelo.criterion == parametros["criterion"] and modelo.max_features == parametros["max_features"]
    assert modelo.class_weight == parametros["class_weight"] and modelo.random_state == parametros["semente"]
    assert list(modelo.feature_names_in_) == pacote["colunas"], "o modelo foi treinado com outras colunas"
    return modelo


def _sha256(arquivo) -> str:
    """SHA-256 do arquivo inteiro, como o `shasum -a 256` de macOS e o `sha256sum` de Linux."""
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()
