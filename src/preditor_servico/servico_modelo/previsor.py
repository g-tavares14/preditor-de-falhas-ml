"""O previsor: valida o pedido, monta o X de 10 colunas e devolve a classe e as probabilidades (SPEC-api-csharp.md)."""

import math

import numpy as np
import pandas as pd

from preditor_servico.servico_modelo import parametros
from preditor_servico.modelo_exportado import COLUNAS_DO_MODELO, ModeloExportado


class PedidoInvalido(ValueError):
    """O corpo do pedido não está no formato combinado (vira 400 no servidor)."""


class Previsor:
    def __init__(self, exportado: ModeloExportado) -> None:
        self.exportado = exportado
        self.modelo = exportado.modelo
        self.colunas = list(COLUNAS_DO_MODELO)
        self.classes = [str(classe) for classe in self.modelo.classes_]

    def montar_x(self, medicoes: object) -> pd.DataFrame:
        """O X do pedido, na ordem das colunas do modelo. Coluna ausente ou `null` fica NaN: o modelo a aceita (RFC §8.3)."""
        if not isinstance(medicoes, list) or not medicoes:
            raise PedidoInvalido("'medicoes' tem de ser uma lista com pelo menos uma medição.")
        if len(medicoes) > parametros.MAXIMO_MEDICOES:
            raise PedidoInvalido(f"No máximo {parametros.MAXIMO_MEDICOES} medições por pedido (vieram {len(medicoes)}).")

        linhas = []
        for posicao, medicao in enumerate(medicoes):
            if not isinstance(medicao, dict):
                raise PedidoInvalido(f"A medição {posicao} não é um objeto.")
            desconhecidas = sorted(set(medicao) - set(self.colunas))
            if desconhecidas:
                raise PedidoInvalido(f"A medição {posicao} tem colunas que o modelo não usa: {', '.join(desconhecidas)}.")
            linha = []
            for coluna in self.colunas:
                valor = medicao.get(coluna)
                # `bool` é subclasse de `int` em Python: sem esta exclusão, `true` entraria como 1.
                if valor is not None and (isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor)):
                    raise PedidoInvalido(f"A medição {posicao}, coluna '{coluna}': esperado um número finito ou null.")
                linha.append(np.nan if valor is None else float(valor))
            linhas.append(linha)
        return pd.DataFrame(linhas, columns=self.colunas, dtype="float64")

    def prever(self, medicoes: object) -> list[dict]:
        """Uma previsão por medição, na mesma ordem do pedido."""
        x = self.montar_x(medicoes)
        probabilidades = self.modelo.predict_proba(x)
        # A floresta prevê a classe de maior probabilidade média (é o que o `predict` do scikit-learn faz).
        return [
            {
                "classe": self.classes[int(np.argmax(linha))],
                "probabilidades": {classe: float(valor) for classe, valor in zip(self.classes, linha)},
            }
            for linha in probabilidades
        ]

    def ficha(self) -> dict:
        """O que o `/saude` e o `/modelo` da API mostram: qual modelo está carregado (o mesmo bloco que o `replay.json` leva)."""
        return {"modelo": {**self.exportado.bloco(), "classes": self.classes}}
