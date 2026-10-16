"""O serviço ao vivo: busca os resultados novos do Atlas, prevê com a Random Forest exportada e confere (SPEC-ao-vivo.md).

Duas fases por fluxo (`prb_id|dst_addr|msm_id`):
1. `preparar`: sorteia as sondas, baixa as últimas 108 h antes de T0, calcula a ficha de cada fluxo e a congela no
   `estado.json`. Nada que chegue depois de T0 entra nela.
2. `ServicoAoVivo.ciclo`: busca o que chegou, recalcula o X e o Y com o motor (`calculo.py`), prevê as medições novas (a
   previsão é congelada no instante em que a medição chega) e grava os arquivos. Quando a 3ª medição seguinte chega, o
   `status_atual` dela vira o futuro verdadeiro e a previsão é conferida.
"""

import json
import time

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from preditor import config
from preditor.aovivo import pagina, parametros
from preditor.aovivo.atlas import ClienteAtlas, ErroDaApi, ler_resultado
from preditor.aovivo.calculo import Baseline, Features, Rotulo
from preditor.aovivo.selecao import Selecao
from preditor.modelo.dados import DadosModelo
from preditor.visualizacao.exportacao import ExportadorReplay
from preditor.visualizacao.modelo_exportado import ModeloExportado

COLUNAS_CRUAS = ["fluxo_id", "prb_id", "dst_addr", "msm_id", "t", "rtt", "jitter", "perda_pct", "timeout_atual"]
COLUNAS_DA_FICHA = ["n_medicoes", "n_validos", "mediana", "iqr", "jitter_tipico", "perda_tipica", "mad", "baseline_insuficiente"]
FALHAS_SEGUIDAS_MAXIMAS = 30  # com 1 consulta por minuto, 30 min sem a API: o serviço para em vez de girar à toa


# --- Fase 1: preparar -------------------------------------------------------------------------------------------


def preparar(cliente: ClienteAtlas, exportado: ModeloExportado, quantas: int, paises: tuple[str, ...], retroativo_horas: float) -> dict:
    """Sorteia as sondas, congela a ficha de cada fluxo e grava o `estado.json`. Devolve o estado."""
    selecao = Selecao(cliente)
    candidatas = selecao.candidatas(paises)
    if not candidatas:
        raise SystemExit(f"Nenhuma sonda de {', '.join(paises)} participa das 6 medições (fora as do treino). Tente outros países com --paises.")
    escolhidas = selecao.sortear(candidatas, quantas)
    print(f"{len(candidatas)} sondas candidatas em {', '.join(paises)}; sorteio (semente {config.SEMENTE}): {len(escolhidas)} sondas")
    for prb_id, sonda in escolhidas.items():
        print(f"  sonda {prb_id}: {sonda['pais']} ({sonda['latitude']:.2f}, {sonda['longitude']:.2f}), AS{sonda['asn']}")

    # T0 = agora (menos o retroativo, se pedido): o baseline são as 108 h até T0, e T0 em diante é o "ao vivo".
    t0 = int(time.time() - retroativo_horas * 3600)
    print(f"Baixando as {config.HORAS_PERIODO_A} h de baseline antes de T0 ({pagina._instante(t0)})...")
    historico = selecao.baixar_historico(list(escolhidas), t0)
    parametros.PASTA.mkdir(parents=True, exist_ok=True)
    historico.to_parquet(parametros.ARQUIVO_HISTORICO, index=False)

    ficha = Baseline.calcular(historico)
    esperados = {f"{prb_id}|{destino['dst_addr']}|{msm_id}" for prb_id in escolhidas for msm_id, destino in parametros.DESTINOS.items()}
    insuficientes = sorted(ficha.index[ficha["baseline_insuficiente"]])
    sem_dados = sorted(esperados - set(ficha.index))
    utilizaveis = len(ficha) - len(insuficientes)
    print(f"Baseline: {utilizaveis} fluxos com ficha, {len(insuficientes)} com baseline insuficiente (< {config.PISO_RTT_VALIDOS} RTT válidos), {len(sem_dados)} sem nenhuma medição.")
    for fluxo_id in insuficientes:
        print(f"  fora: {fluxo_id} ({int(ficha.loc[fluxo_id, 'n_validos'])} RTT válidos)")
    for fluxo_id in sem_dados:
        print(f"  fora: {fluxo_id} (sem medição nas 108 h)")
    if utilizaveis == 0:
        raise SystemExit("Nenhum fluxo tem baseline suficiente: nada para prever.")

    estado = {
        "criado_em": pagina._instante(int(time.time())),
        "t0": t0,
        "semente": config.SEMENTE,
        "paises": list(paises),
        "modelo_sha256": exportado.sha256,
        "sondas": {str(prb_id): sonda for prb_id, sonda in escolhidas.items()},
        "fichas": {
            fluxo_id: {coluna: (None if pd.isna(valor) else (bool(valor) if coluna == "baseline_insuficiente" else float(valor))) for coluna, valor in linha.items()}
            for fluxo_id, linha in ficha[COLUNAS_DA_FICHA].iterrows()
        },
        "insuficientes": insuficientes,
        "sem_dados": sem_dados,
    }
    parametros.ARQUIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return estado


def ler_estado() -> dict | None:
    return json.loads(parametros.ARQUIVO_ESTADO.read_text(encoding="utf-8")) if parametros.ARQUIVO_ESTADO.exists() else None


def ficha_do_estado(estado: dict) -> pd.DataFrame:
    """A ficha congelada de volta em DataFrame (índice = `fluxo_id`); o `null` do JSON volta a ser NaN."""
    ficha = pd.DataFrame.from_dict(estado["fichas"], orient="index", columns=COLUNAS_DA_FICHA)
    ficha["baseline_insuficiente"] = ficha["baseline_insuficiente"].astype(bool)
    return ficha.astype({coluna: "float64" for coluna in COLUNAS_DA_FICHA if coluna != "baseline_insuficiente"})


# --- Fase 2: o laço ----------------------------------------------------------------------------------------------


class ServicoAoVivo:
    def __init__(self, cliente: ClienteAtlas, exportado: ModeloExportado, estado: dict) -> None:
        self.cliente = cliente
        self.exportado = exportado
        self.modelo = exportado.modelo
        self.colunas = DadosModelo.colunas_ajustadas()
        self.estado = estado
        self.t0 = int(estado["t0"])
        self.ficha = ficha_do_estado(estado)
        self.utilizaveis = set(self.ficha.index[~self.ficha["baseline_insuficiente"]])
        self.sondas = sorted(int(prb_id) for prb_id in estado["sondas"])
        self.bloco_do_modelo = ExportadorReplay.bloco_modelo(exportado)
        self.cruas, self.previsoes = self._retomar()
        self.falhas_seguidas = 0
        # A mediana medida não pode ser menor que o mínimo da física: se for, o cartão da página mostraria algo impossível.
        impossiveis = pagina.fluxos_impossiveis(pagina.montar_fluxos(estado, self.ficha))
        if impossiveis:
            print(f"Atenção: {len(impossiveis)} fluxos com mediana abaixo do RTT mínimo da física (coordenada errada ou IP anycast): {impossiveis}")

    # --- Estado em disco -------------------------------------------------------------------------------------------

    @staticmethod
    def _retomar() -> tuple[pd.DataFrame, dict]:
        """As medições ao vivo e as previsões já emitidas, se o serviço já rodou; senão, vazio."""
        if not parametros.ARQUIVO_MEDICOES.exists():
            return pd.DataFrame(columns=COLUNAS_CRUAS).astype({"t": "int64"}), {}
        lidas = pd.read_parquet(parametros.ARQUIVO_MEDICOES)
        previsoes = {(linha.fluxo_id, int(linha.t)): linha.previsto for linha in lidas.itertuples() if isinstance(linha.previsto, str)}
        return lidas[COLUNAS_CRUAS].reset_index(drop=True), previsoes

    def _gravar_medicoes(self) -> None:
        tabela = self.cruas.copy()
        tabela["previsto"] = [self.previsoes.get((linha.fluxo_id, int(linha.t))) for linha in tabela.itertuples()]
        tabela.to_parquet(parametros.ARQUIVO_MEDICOES, index=False)

    # --- Um ciclo ----------------------------------------------------------------------------------------------------

    def _buscar(self, inicio: int, fim: int) -> list[dict]:
        """Os resultados das sondas nas 6 medições entre `inicio` e `fim`, em janelas de `HORAS_POR_PEDIDO`."""
        passo = parametros.HORAS_POR_PEDIDO * 3600
        linhas = []
        for msm_id in parametros.DESTINOS:
            de = inicio
            while de <= fim:
                ate = min(de + passo, fim)
                lidas = (ler_resultado(resultado) for resultado in self.cliente.resultados(msm_id, self.sondas, de, ate))
                linhas.extend(linha for linha in lidas if linha is not None)
                de = ate + 1
        return linhas

    def ciclo(self) -> dict:
        """Uma volta: busca, calcula, prevê o que chegou, grava. Devolve os números da volta para a linha do terminal."""
        agora = int(time.time())
        ultimo = int(self.cruas["t"].max()) if len(self.cruas) else self.t0
        # Recomeça um pouco antes do último `t` visto: resultados atrasados aparecem depois dos mais novos. O que já está na
        # tabela não é duplicado (a chave é fluxo + `t`). Nunca antes de T0: o que é de antes é do baseline.
        recebidas = self._buscar(max(self.t0 + 1, ultimo - parametros.SOBREPOSICAO_S), agora)

        novas = pd.DataFrame(recebidas, columns=COLUNAS_CRUAS)
        novas = novas[(novas["t"] > self.t0) & novas["fluxo_id"].isin(self.utilizaveis)].drop_duplicates(["fluxo_id", "t"])
        if len(self.cruas):
            ja_vistas = pd.MultiIndex.from_frame(self.cruas[["fluxo_id", "t"]])
            novas = novas[~pd.MultiIndex.from_frame(novas[["fluxo_id", "t"]]).isin(ja_vistas)]
        if len(novas):
            self.cruas = pd.concat([self.cruas, novas[COLUNAS_CRUAS]], ignore_index=True) if len(self.cruas) else novas[COLUNAS_CRUAS].reset_index(drop=True)

        if self.cruas.empty:
            return {"novas": 0, "total": 0}
        calculado = Rotulo.rotular(Features.construir(self.cruas, self.ficha))
        emitidas = self._prever_pendentes(calculado)
        calculado["previsto"] = [self.previsoes[(linha.fluxo_id, int(linha.t))] for linha in calculado.itertuples()]
        placar = self._placar(calculado)
        self._gravar(calculado, agora, placar)
        self._verificar_saidas(calculado, placar)
        return {"novas": emitidas, "total": len(calculado), **placar}

    def _prever_pendentes(self, calculado: pd.DataFrame) -> int:
        """Prevê as medições que ainda não têm previsão e a congela: ela nunca muda depois de emitida."""
        chaves = list(zip(calculado["fluxo_id"], calculado["t"].astype(int)))
        pendentes = [i for i, chave in enumerate(chaves) if chave not in self.previsoes]
        if pendentes:
            x = calculado.iloc[pendentes][self.colunas].astype("float64")  # NaN continua NaN: o modelo o aceita (RFC §8.3)
            for i, classe in zip(pendentes, self.modelo.predict(x)):
                self.previsoes[chaves[i]] = str(classe)
        return len(pendentes)

    # --- Placar --------------------------------------------------------------------------------------------------------

    @staticmethod
    def _placar(calculado: pd.DataFrame) -> dict:
        """O modelo e a persistência ("o futuro é igual ao agora") nas medições já conferidas: acerto e F1 macro."""
        conferidas = calculado[calculado["status_futuro"].notna()]
        n = len(conferidas)
        if n == 0:
            return {"conferidas": 0}
        classes = list(config.CLASSES)
        verdadeiro = conferidas["status_futuro"]
        resultado = {"conferidas": n}
        for nome, previsto in (("modelo", conferidas["previsto"]), ("persistencia", conferidas["status_atual"])):
            resultado[f"acerto_{nome}"] = float((previsto == verdadeiro).mean())
            resultado[f"f1_{nome}"] = float(f1_score(verdadeiro, previsto, labels=classes, average="macro", zero_division=0))
        resultado["matriz_modelo"] = pd.crosstab(verdadeiro, conferidas["previsto"]).reindex(index=classes, columns=classes, fill_value=0).to_numpy().tolist()
        resultado["futuro_por_classe"] = {classe: int((verdadeiro == classe).sum()) for classe in classes}
        return resultado

    # --- Saídas --------------------------------------------------------------------------------------------------------

    def _gravar(self, calculado: pd.DataFrame, agora: int, placar: dict) -> None:
        self._gravar_medicoes()
        conferivel = calculado["status_futuro"].notna()
        tabela = pd.DataFrame(
            {
                "fluxo_id": calculado["fluxo_id"],
                "instante_utc": [pagina._instante(int(t)) for t in calculado["t"]],
                "rtt_ms": calculado["rtt"],
                "status_atual": calculado["status_atual"],
                "previsto": calculado["previsto"],
                "status_futuro": calculado["status_futuro"],
                "instante_do_futuro_utc": [pagina._instante(int(t)) if pd.notna(t) else "" for t in calculado["t_futuro"]],
                "modelo_acertou": np.where(conferivel, calculado["previsto"] == calculado["status_futuro"], None),
                "persistencia_acertou": np.where(conferivel, calculado["status_atual"] == calculado["status_futuro"], None),
            }
        ).sort_values(["instante_utc", "fluxo_id"])
        tabela.to_csv(parametros.ARQUIVO_PREVISOES, index=False)

        resumo = {
            "gerado_em": pagina._instante(agora),
            "t0": pagina._instante(self.t0),
            "fluxos": len(self.utilizaveis),
            "sondas": len(self.sondas),
            "medicoes": len(calculado),
            **placar,
        }
        parametros.ARQUIVO_RESUMO.write_text(json.dumps(resumo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        pagina.gravar(pagina.montar(calculado, self.previsoes, self.estado, self.ficha, self.bloco_do_modelo, agora))

    @staticmethod
    def _verificar_saidas(calculado: pd.DataFrame, placar: dict) -> None:
        """Lê de volta o que foi gravado e confere: CSV e JSON da página têm as mesmas medições e o placar fecha com o CSV."""
        tabela = pd.read_csv(parametros.ARQUIVO_PREVISOES)
        documento = json.loads(parametros.ARQUIVO_PAGINA.read_text(encoding="utf-8"))
        na_pagina = pagina.recortar(calculado)  # o JSON da página leva só as últimas horas; o CSV leva tudo
        assert len(tabela) == len(calculado), "o CSV e o cálculo têm números diferentes de medições"
        assert len(documento["medicoes"]) == len(na_pagina), "o JSON da página e o cálculo têm números diferentes de medições"
        conferidas = tabela["status_futuro"].notna()
        assert int(conferidas.sum()) == placar.get("conferidas", 0), "o número de conferidas do CSV diverge do placar"
        assert sum(m["conferivel"] for m in documento["medicoes"]) == int(na_pagina["status_futuro"].notna().sum()), "as conferíveis do JSON divergem"
        assert [m["previsto"] for m in documento["medicoes"]] == list(na_pagina.sort_values(["t", "fluxo_id"], kind="stable")["previsto"]), (
            "a previsão do JSON da página difere da emitida"
        )
        if conferidas.any():
            do_csv = tabela[conferidas]
            assert abs((do_csv["previsto"] == do_csv["status_futuro"]).mean() - placar["acerto_modelo"]) < 1e-12, "acerto do modelo diverge do CSV"
            assert abs((do_csv["status_atual"] == do_csv["status_futuro"]).mean() - placar["acerto_persistencia"]) < 1e-12, "acerto da persistência diverge do CSV"

    # --- O laço ----------------------------------------------------------------------------------------------------------

    def rodar(self, ciclos: int | None) -> None:
        """Gira até `ciclos` voltas (ou até o Ctrl+C). Uma falha da API não derruba o serviço: tenta de novo na volta seguinte."""
        volta = 0
        try:
            while ciclos is None or volta < ciclos:
                inicio = time.monotonic()
                try:
                    numeros = self.ciclo()
                    self.falhas_seguidas = 0
                    print(self._linha(numeros), flush=True)
                except ErroDaApi as erro:
                    self.falhas_seguidas += 1
                    print(f"[{time.strftime('%H:%M:%S')}] a API falhou ({self.falhas_seguidas}ª seguida): {erro}", flush=True)
                    if self.falhas_seguidas >= FALHAS_SEGUIDAS_MAXIMAS:
                        raise SystemExit(f"{FALHAS_SEGUIDAS_MAXIMAS} falhas seguidas da API: encerrando. Os dados até aqui estão em {parametros.PASTA}.")
                volta += 1
                if ciclos is None or volta < ciclos:
                    time.sleep(max(0.0, parametros.INTERVALO_CONSULTA_S - (time.monotonic() - inicio)))
        except KeyboardInterrupt:
            print("\nServiço encerrado. Os dados estão em", parametros.PASTA)

    @staticmethod
    def _linha(numeros: dict) -> str:
        """Uma linha por volta: quantas medições chegaram e o placar do modelo contra o palpite simples."""
        relogio = time.strftime("%H:%M:%S")
        if numeros["total"] == 0:
            return f"[{relogio}] ainda sem medições novas depois de T0"
        base = f"[{relogio}] +{numeros['novas']} medições, {numeros['total']} no total"
        if numeros["conferidas"] == 0:
            return base + " | nenhuma previsão conferida ainda (a 3ª medição seguinte leva ~12 min)"
        return (
            f"{base} | conferidas {numeros['conferidas']}: modelo {numeros['acerto_modelo']:.1%} (F1 {numeros['f1_modelo']:.3f}) × "
            f"persistência {numeros['acerto_persistencia']:.1%} (F1 {numeros['f1_persistencia']:.3f})"
        )
