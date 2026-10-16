"""Conferência do microserviço do modelo: pela rede, ele devolve o mesmo que o modelo recarregado (SPEC-api-csharp.md, "Verificação").

`uv run python -m preditor_analise.conferir_servico`. Fica na análise porque lê o Gold (o `preditor_servico` não o lê).

Sobe o servidor numa porta livre, manda a amostra de treino e validação (nunca o teste) e exige 0 diferenças. A mesma amostra,
com a resposta esperada, vai para o `paridade.json`, que o teste da API em C# usa para provar que o C# não muda nada.
"""

import http.client
import json
import sys
import threading

import numpy as np
import pandas as pd

from preditor_analise import config
from preditor_analise.modelo.dados import DadosModelo
from preditor_servico.modelo_exportado import ModeloExportado
from preditor_servico.servico_modelo import parametros
from preditor_servico.servico_modelo.previsor import Previsor
from preditor_servico.servico_modelo.servidor import criar_servidor

TOLERANCIA_PROBABILIDADE = 1e-12  # o JSON devolve o double do Python inteiro (repr); a conta é a mesma


class Conferencia:
    def __init__(self, previsor: Previsor) -> None:
        self.previsor = previsor

    def rodar(self) -> None:
        amostra = self._amostra()
        esperado = self._esperado(amostra)
        servidor = criar_servidor(self.previsor, "127.0.0.1", 0)  # porta 0 = o sistema escolhe uma livre
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        porta = servidor.server_address[1]
        try:
            self._comparar_com_o_modelo(porta, amostra, esperado)
            self._conferir_recusas(porta)
        finally:
            servidor.shutdown()
            servidor.server_close()
        assert sys.modules.get("pyspark") is None, "o microserviço não pode carregar o PySpark"
        self._gravar_paridade(amostra, esperado)

    # --- A amostra ----------------------------------------------------------------------------------------------

    def _amostra(self) -> pd.DataFrame:
        """~300 linhas de treino e validação: as com valor ausente (onde o ONNX divergia) e algumas de cada classe prevista."""
        dados = DadosModelo().carregar()
        colunas = self.previsor.colunas
        conjunto = pd.concat([dados.x_ajustado("treino")[colunas], dados.x_ajustado("validacao")[colunas]], ignore_index=True)
        previsto = self.previsor.modelo.predict(conjunto)
        sorteio = np.random.default_rng(config.SEMENTE)

        com_nan = np.flatnonzero(conjunto.isna().any(axis=1).to_numpy())
        escolhidas = list(sorteio.choice(com_nan, size=min(parametros.LINHAS_COM_NAN, len(com_nan)), replace=False))
        sem_nan = ~conjunto.isna().any(axis=1).to_numpy()
        for classe in self.previsor.classes:
            candidatas = np.flatnonzero(sem_nan & (previsto == classe))
            escolhidas += list(sorteio.choice(candidatas, size=min(parametros.LINHAS_POR_CLASSE, len(candidatas)), replace=False))

        amostra = conjunto.iloc[sorted(escolhidas)].reset_index(drop=True)  # na ordem do conjunto: a amostra não depende do sorteio
        assert set(self.previsor.modelo.predict(amostra)) == set(self.previsor.classes), "a amostra não tem as três classes"
        assert amostra.isna().any(axis=1).sum() >= min(parametros.LINHAS_COM_NAN, len(com_nan)), "a amostra perdeu as linhas com NaN"
        return amostra

    def _esperado(self, amostra: pd.DataFrame) -> list[dict]:
        """O que o modelo recarregado, direto, diz para cada linha: é a referência."""
        modelo = self.previsor.modelo
        classes = modelo.predict(amostra)
        probabilidades = modelo.predict_proba(amostra)
        return [
            {"classe": str(classe), "probabilidades": {nome: float(valor) for nome, valor in zip(self.previsor.classes, linha)}}
            for classe, linha in zip(classes, probabilidades)
        ]

    @staticmethod
    def _como_pedido(amostra: pd.DataFrame) -> list[dict]:
        """Cada linha como a API manda: NaN vira `null`."""
        return [{coluna: (None if pd.isna(valor) else float(valor)) for coluna, valor in linha.items()} for linha in amostra.to_dict("records")]

    # --- As conferências ----------------------------------------------------------------------------------------

    def _chamar(self, porta: int, metodo: str, caminho: str, corpo: bytes | None = None, cabecalhos: dict | None = None) -> tuple[int, dict]:
        conexao = http.client.HTTPConnection("127.0.0.1", porta, timeout=30)
        try:
            conexao.request(metodo, caminho, body=corpo, headers=cabecalhos or {})
            resposta = conexao.getresponse()
            return resposta.status, json.loads(resposta.read())
        finally:
            conexao.close()

    def _comparar_com_o_modelo(self, porta: int, amostra: pd.DataFrame, esperado: list[dict]) -> None:
        corpo = json.dumps({"medicoes": self._como_pedido(amostra)}, allow_nan=False).encode()
        status, resposta = self._chamar(porta, "POST", "/prever", corpo)
        assert status == 200, f"/prever respondeu {status}: {resposta}"
        recebidas = resposta["previsoes"]
        assert len(recebidas) == len(esperado), "o serviço devolveu um número diferente de previsões"
        classes_erradas = sum(r["classe"] != e["classe"] for r, e in zip(recebidas, esperado))
        maior_diferenca = max(abs(r["probabilidades"][c] - e["probabilidades"][c]) for r, e in zip(recebidas, esperado) for c in self.previsor.classes)
        assert classes_erradas == 0, f"{classes_erradas} classes diferentes do modelo recarregado"
        assert maior_diferenca <= TOLERANCIA_PROBABILIDADE, f"probabilidade difere em {maior_diferenca:.2e}"
        assert resposta["modelo"]["sha256"] == self.previsor.exportado.sha256, "o SHA-256 da resposta não é o do arquivo aberto"
        com_nan = int(amostra.isna().any(axis=1).sum())
        print(f"Paridade: {len(esperado)} linhas ({com_nan} com NaN), 0 classes diferentes, maior diferença de probabilidade {maior_diferenca:.1e}")

    def _conferir_recusas(self, porta: int) -> None:
        """Cada pedido torto é recusado com o código certo, e o serviço continua respondendo depois."""
        json_cabecalho = {"Content-Type": "application/json"}
        valida = {"z_robusto": 0.3}
        casos = {
            "JSON quebrado": ("POST", "/prever", b"{nao e json", json_cabecalho, 400),
            "NaN no JSON": ("POST", "/prever", b'{"medicoes":[{"z_robusto":NaN}]}', json_cabecalho, 400),
            "Infinity no JSON": ("POST", "/prever", b'{"medicoes":[{"perda_pct":Infinity}]}', json_cabecalho, 400),
            "sem medicoes": ("POST", "/prever", b'{"medicoes":[]}', json_cabecalho, 400),
            "corpo que não é objeto": ("POST", "/prever", b"[1,2]", json_cabecalho, 400),
            "coluna desconhecida": ("POST", "/prever", json.dumps({"medicoes": [{"rtt": 10.0}]}).encode(), json_cabecalho, 400),
            "booleano no lugar de número": ("POST", "/prever", json.dumps({"medicoes": [{"timeout_atual": True}]}).encode(), json_cabecalho, 400),
            "texto no lugar de número": ("POST", "/prever", json.dumps({"medicoes": [{"z_robusto": "3"}]}).encode(), json_cabecalho, 400),
            "linhas demais": ("POST", "/prever", json.dumps({"medicoes": [valida] * (parametros.MAXIMO_MEDICOES + 1)}).encode(), json_cabecalho, 400),
            "corpo grande demais": ("POST", "/prever", None, {"Content-Length": str(parametros.MAXIMO_CORPO_BYTES + 1)}, 413),
            "rota que não existe": ("GET", "/outra", None, {}, 404),
            "método que não existe": ("DELETE", "/prever", None, {}, 405),
        }
        for nome, (metodo, caminho, corpo, cabecalhos, esperado) in casos.items():
            status, resposta = self._chamar(porta, metodo, caminho, corpo, cabecalhos)
            assert status == esperado, f"'{nome}': esperado {esperado}, veio {status} ({resposta})"
        # O pedido mínimo (uma coluna só, o resto ausente) tem de passar: valor ausente é permitido.
        status, resposta = self._chamar(porta, "POST", "/prever", json.dumps({"medicoes": [valida]}).encode(), json_cabecalho)
        assert status == 200 and len(resposta["previsoes"]) == 1, f"pedido com colunas ausentes: {status} {resposta}"
        status, resposta = self._chamar(porta, "GET", "/saude")
        assert status == 200 and resposta["status"] == "ok" and resposta["modelo"]["sha256"] == self.previsor.exportado.sha256
        print(f"Recusas: {len(casos)} pedidos tortos com o código certo; pedido só com uma coluna aceito; /saude ok")

    # --- A saída ------------------------------------------------------------------------------------------------

    def _gravar_paridade(self, amostra: pd.DataFrame, esperado: list[dict]) -> None:
        documento = {
            "modelo_sha256": self.previsor.exportado.sha256,
            "colunas": self.previsor.colunas,
            "amostra": [{"entrada": entrada, "esperado": previsto} for entrada, previsto in zip(self._como_pedido(amostra), esperado)],
        }
        parametros.ARQUIVO_PARIDADE.parent.mkdir(parents=True, exist_ok=True)
        parametros.ARQUIVO_PARIDADE.write_text(json.dumps(documento, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        print(f"Gravado: {parametros.ARQUIVO_PARIDADE} ({len(esperado)} linhas)")


def main() -> None:
    # O SHA-256 é conferido antes de abrir o pickle; sem os arquivos, a mensagem diz qual comando rodar.
    Conferencia(Previsor(ModeloExportado.ler())).rodar()


if __name__ == "__main__":
    main()
