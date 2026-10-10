"""Teste único da Tarefa 5 (SPEC-teste-final.md): o ensaio e a abertura, com o mesmo caminho de código. Mede, confere, grava.

O `ensaio` (`teste --ensaio`) roda o MESMO caminho nas linhas da VALIDAÇÃO, confere os números com `comparacao_modelos.csv`
e só então grava o carimbo `ensaio_ok.json`. Nunca toca o bloco de teste.

A abertura (`teste --abrir-o-teste`) é o único caminho que lê o bloco de teste, e só depois de: carimbo válido (SHA-256 do
modelo, da escolha e do código de medição), trava ausente e `TESTE_ABERTO.json` gravado em `em_andamento` ANTES da leitura.
Ao fim, grava as saídas e troca a trava para `concluido`. Se uma checagem falha, a trava fica `em_andamento` e nada mais
é gravado. Este módulo é o único que importa `dados_teste.py` (conferido por `grep`). Não chama `fit`: o modelo medido é o
arquivo `modelo_final.joblib` exportado, com o SHA-256 conferido contra o LEIA-ME antes de abrir.
"""

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from preditor import config
from preditor.modelo.avaliacao import Avaliacao, CasoErro, ErroConcreto
from preditor.modelo.comparacao import f1_macro_das_matrizes, ic_pareado, quadro_comparacao
from preditor.modelo.dados import DadosModelo
from preditor.modelo.dados_teste import BlocoLido, DadosTeste
from preditor.modelo.floresta import Floresta

# Os dois casos concretos do teste (SPEC-teste-final.md, "Regras fixadas", item 5). O erro tem o mesmo critério de
# `Avaliacao.CASOS_ERRO[1]` (FALHA de caminho curto que o modelo mandou para OK). O acerto é o caso novo: OK previsto OK,
# em caminho longo e estável. O `maior_rtt` do acerto não vem da spec: espelha o primeiro caso da validação (decisão do dono).
CASO_ACERTO = CasoErro("Acerto em caminho longo e estável (OK previsto OK)", True, True, "OK", "OK", maior_rtt=True)
CASO_ERRO = CasoErro("FALHA real prevista como OK", False, False, "FALHA", "OK", maior_rtt=False)
CASOS_TESTE = (CASO_ACERTO, CASO_ERRO)

# Arquivos cujo conteúdo define a medição. O carimbo guarda o SHA-256 de cada um: se mudou depois do ensaio, a abertura
# recusa e o ensaio precisa rodar de novo.
PASTA_MODELO = Path(__file__).resolve().parent
CODIGO_DE_MEDICAO = (
    PASTA_MODELO / "execucao_teste.py",
    PASTA_MODELO / "dados_teste.py",
    PASTA_MODELO / "dados.py",
    PASTA_MODELO / "avaliacao.py",
    PASTA_MODELO / "comparacao.py",
    PASTA_MODELO / "floresta.py",
    Path(config.__file__).resolve(),
)

# As métricas que a comparação grava por modelo: o teste e a validação são lidos com as mesmas colunas.
METRICAS_COMPARADAS = (
    "f1_macro", "f1_OK", "f1_RISCO", "f1_FALHA", "recall_FALHA", "recall_RISCO",
    "n_OK_para_FALHA", "acerto_OK_para_FALHA", "n_FALHA_para_OK", "acerto_FALHA_para_OK",
    "acerto_futuro_igual", "acerto_futuro_muda",
)

# A declaração (SPEC-teste-final.md, regra 4). Leitura fixada pelo dono em 10/10/2026: só o limite INFERIOR do IC maior que
# zero declara preditor. IC todo abaixo de zero, ou cruzando o zero, não é preditor.
DECLARACAO_PREDITOR = "preditor de 12 minutos"
DECLARACAO_DETECTOR = "detector do estado atual"
REGRA_DECLARACAO = (
    "preditor de 12 minutos só se o limite inferior do IC 95 % do ganho de F1 macro sobre a persistência for maior que zero; "
    "IC abaixo de zero ou cruzando o zero é detector do estado atual"
)


@dataclass(frozen=True)
class Saidas:
    """Onde a abertura lê o carimbo, grava a trava e grava as saídas. A produção usa `padrao()`; a verificação, `em()`."""

    carimbo: Path
    trava: Path
    matriz: Path
    metricas: Path
    ic: Path
    casos: Path
    resultado: Path

    @staticmethod
    def padrao() -> "Saidas":
        return Saidas(
            config.ARQUIVO_ENSAIO_OK, config.ARQUIVO_TESTE_ABERTO, config.ARQUIVO_MATRIZ_TESTE,
            config.ARQUIVO_METRICAS_TESTE, config.ARQUIVO_IC_GANHO_TESTE, config.ARQUIVO_CASOS_TESTE,
            config.ARQUIVO_RESULTADO_TESTE,
        )

    @staticmethod
    def em(pasta: Path) -> "Saidas":
        """Os mesmos nomes de `padrao`, numa pasta temporária: a trava e as saídas nunca tocam `data/modelo/teste/`."""
        padrao = Saidas.padrao()
        return Saidas(*(pasta / caminho.name for caminho in (
            padrao.carimbo, padrao.trava, padrao.matriz, padrao.metricas, padrao.ic, padrao.casos, padrao.resultado,
        )))


@dataclass(frozen=True)
class Medicao:
    """O que se mede num bloco: as previsões, as métricas, as transições, a linha da comparação, o IC, os casos e a mediana."""

    previstos: dict
    resultados: dict
    mudancas: dict
    comparacao: pd.DataFrame
    ic: pd.DataFrame
    casos: list
    mediana: float


# --------------------------------------------------------------------------------------------------------------------
# Trava e carimbo: funções que recebem o caminho (a verificação usa pastas temporárias)
# --------------------------------------------------------------------------------------------------------------------
def recusar_se_aberto(trava: Path) -> None:
    """Recusa a abertura se a trava existe, em qualquer estado. Antes desta checagem nada é lido nem gravado."""
    if not trava.exists():
        return
    try:
        estado = json.loads(trava.read_text(encoding="utf-8")).get("estado", "sem estado")
    except (ValueError, AttributeError):
        estado = "ilegível"
    raise SystemExit(
        f"O teste já foi aberto: {trava.name} existe (estado {estado}). Não há segunda abertura pelo código. "
        "Apagar a trava é decisão do dono e deve ser registrada no relatório."
    )


def abrir_trava(trava: Path, conteudo: dict) -> None:
    """Cria a trava de forma exclusiva (modo `x`): se outra abertura a criou antes, recusa e não sobrescreve."""
    trava.parent.mkdir(parents=True, exist_ok=True)
    try:
        with trava.open("x", encoding="utf-8") as arquivo:
            arquivo.write(_json(conteudo))
    except FileExistsError:
        recusar_se_aberto(trava)  # o arquivo existe, então a recusa sempre sai daqui


def concluir_trava(trava: Path, conteudo: dict) -> None:
    """Troca `em_andamento` por `concluido`. Só uma trava em andamento pode ser concluída."""
    estado = json.loads(trava.read_text(encoding="utf-8"))["estado"]
    assert estado == config.ESTADO_EM_ANDAMENTO, f"a trava está em {estado}; só uma abertura em andamento conclui"
    trava.write_text(_json(conteudo), encoding="utf-8")


def conferir_carimbo(carimbo: Path, esperado: dict) -> None:
    """O `ensaio_ok.json` tem de existir e bater com o estado de agora (modelo, escolha e código de medição)."""
    if not carimbo.exists():
        raise SystemExit(
            f"Não há {carimbo.name}: o ensaio ainda não passou. Rode antes: uv run python -m preditor teste --ensaio"
        )
    try:
        gravado = json.loads(carimbo.read_text(encoding="utf-8"))
    except ValueError:
        raise SystemExit(f"{carimbo.name} está ilegível. Rode o ensaio de novo.") from None
    diferentes = [chave for chave in esperado if gravado.get(chave) != esperado[chave]]
    if diferentes:
        raise SystemExit(
            f"{carimbo.name} não bate com o estado atual em {diferentes}: o modelo ou o código de medição mudou depois "
            "do ensaio. Rode o ensaio de novo."
        )


class ExecucaoTeste:
    def executar(self, *, ensaio: bool) -> None:
        if ensaio:
            self._ensaio()
            return
        # A abertura de verdade: o único caminho que lê o bloco de teste, com a trava e o carimbo na frente.
        self._abrir(
            config.BLOCO_TESTE,
            Saidas.padrao(),
            contar_n=lambda: DadosTeste(config.BLOCO_TESTE).contar(),
            n_referencia=lambda: DadosModelo().carregar().n_teste,
        )

    # ----------------------------------------------------------------------------------------------------------------
    # Ensaio: o mesmo caminho do teste, nas linhas da validação
    # ----------------------------------------------------------------------------------------------------------------
    def _ensaio(self) -> None:
        validacao = config.BLOCO_VALIDACAO
        print("Teste único, ENSAIO nas linhas da VALIDAÇÃO (o teste não é lido nem medido aqui).")
        modelo, escolha, sha_modelo = self._carregar_modelo()

        # 1. Linhas da validação: X de 10 colunas, y, status_atual e localização (mesmas regras de DadosModelo).
        bloco = DadosTeste(validacao).carregar()
        # 2. As mesmas contas para o modelo e a persistência (ver `_medir`), nas mesmas linhas.
        medicao = self._medir(bloco, modelo, validacao, liberar=False)
        # 3. Fluxos e casos já estão em `medicao`; a contagem de fluxos confere baseline e treino (sem o teste).
        fluxos = self._contar_fluxos(bloco, None)
        # 4. Tudo confere com o que o `comparar` gravou (lido do disco, não digitado). Só então imprime e grava o carimbo.
        self._conferir_com_csv(medicao.comparacao, medicao.resultados, medicao.mudancas, medicao.ic, bloco.y)
        self._imprimir(medicao, fluxos, escolha, "validação (ensaio)", len(bloco.y))
        self._gravar_carimbo(sha_modelo, escolha, len(bloco.y))
        print("\nEnsaio: todas as checagens passaram. Os números da validação são os do `comparar`.")
        print("O teste continua fechado: o ensaio não o lê. Carimbo gravado em data/modelo/teste/ensaio_ok.json.")

    # ----------------------------------------------------------------------------------------------------------------
    # Abertura: recusas, trava, leitura, checagens, gravação, conclusão (SPEC-teste-final.md, "Travas")
    # ----------------------------------------------------------------------------------------------------------------
    def _abrir(self, bloco_nome: str, saidas: Saidas, *, contar_n: Callable[[], int],
               n_referencia: Callable[[], int]) -> None:
        # Ordem fixa: recusas antes de qualquer leitura do bloco; trava antes da leitura; checagens antes da gravação.
        recusar_se_aberto(saidas.trava)
        modelo, escolha, sha_modelo = self._carregar_modelo()
        self._conferir_carimbo(saidas.carimbo, escolha, sha_modelo)

        n = contar_n()  # só a contagem: a trava registra o N antes de qualquer linha ser lida
        inicio = _agora()
        trava = {
            "estado": config.ESTADO_EM_ANDAMENTO, "aberto_em": inicio, "bloco": bloco_nome,
            "sha256_modelo": sha_modelo, "n": n,
        }
        abrir_trava(saidas.trava, trava)

        try:
            self._medir_e_gravar(bloco_nome, modelo, escolha, sha_modelo, saidas, n, n_referencia, inicio)
        except BaseException:
            # Falha no meio: a trava fica em andamento e o código não grava mais nada depois disso. O dono decide.
            print(
                f"\nA abertura falhou depois de gravar a trava: {saidas.trava.name} fica em "
                f"{config.ESTADO_EM_ANDAMENTO}. As checagens rodam antes da gravação; o que já estiver em disco "
                "fica como está. Decisão do dono, a registrar no relatório.",
                file=sys.stderr,
            )
            raise
        concluir_trava(saidas.trava, {**trava, "estado": config.ESTADO_CONCLUIDO, "concluido_em": _agora()})
        print(f"\nTrava {saidas.trava.name}: {config.ESTADO_CONCLUIDO}. Saídas em {saidas.matriz.parent}.")

    def _medir_e_gravar(self, bloco_nome: str, modelo: RandomForestClassifier, escolha: dict, sha_modelo: str,
                        saidas: Saidas, n: int, n_referencia: Callable[[], int], inicio: str) -> None:
        # A ÚNICA leitura das linhas do bloco. Para o teste, só com a liberação explícita, e só depois da trava.
        lido = DadosTeste(bloco_nome).carregar(liberar_teste=True)
        assert len(lido.y) == n, f"o bloco lido tem {len(lido.y)} linhas, e a trava registrou N = {n}"
        referencia = n_referencia()
        assert n == referencia, f"N do bloco ({n}) diferente de DadosModelo.n_teste ({referencia})"
        validacao = DadosTeste(config.BLOCO_VALIDACAO).carregar()

        medicao = self._medir(lido, modelo, bloco_nome, liberar=True)
        fluxos = self._contar_fluxos(validacao, lido)
        self._checar_medicao(medicao, lido, n)  # tudo confere ANTES de gravar
        resultado = self._resultado(bloco_nome, sha_modelo, medicao, n, fluxos, inicio)
        self._gravar_saidas(saidas, medicao, resultado)
        self._verificar_disco(saidas, medicao, resultado, n)
        rotulo = "teste" if bloco_nome == config.BLOCO_TESTE else "validação (ensaio da abertura)"
        self._imprimir(medicao, fluxos, escolha, rotulo, n)

    # ----------------------------------------------------------------------------------------------------------------
    # Medição comum (ensaio e abertura usam esta mesma função)
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _medir(bloco: BlocoLido, modelo: RandomForestClassifier, bloco_nome: str, *, liberar: bool) -> Medicao:
        y, persistencia = bloco.y, bloco.status_atual
        # A previsão é do arquivo medido (sem `fit`); a persistência é o "futuro igual ao agora", nas mesmas linhas.
        previsto = Floresta.prever_em(modelo, bloco.X)
        previstos = {config.MODELO_FLORESTA: previsto, config.MODELO_PERSISTENCIA: persistencia}
        resultados = {m: Avaliacao.medir(y, p, bloco=bloco_nome, liberar_teste=liberar) for m, p in previstos.items()}
        mudancas = {
            m: Avaliacao.quando_muda(y, p, persistencia, bloco=bloco_nome, liberar_teste=liberar)
            for m, p in previstos.items()
        }
        comparacao = quadro_comparacao(
            resultados, mudancas, {m: (None, None, None) for m in previstos}, config.MODELO_FLORESTA
        )
        # IC pareado por fluxo do ganho sobre a persistência (mesma semente e mesmos fluxos que o `comparar`).
        ic, _ = ic_pareado(y, previstos, bloco.localizacao["fluxo_id"],
                           [(config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA)])
        casos = ExecucaoTeste._casos(bloco, previsto)
        return Medicao(previstos, resultados, mudancas, comparacao, ic, casos, bloco.mediana_das_medianas)

    @staticmethod
    def _checar_medicao(medicao: Medicao, lido: BlocoLido, n: int) -> None:
        """Checagens do que foi medido, antes de gravar. Uma falha aqui deixa a trava em andamento."""
        for modelo in (config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA):
            assert medicao.resultados[modelo].n == n, f"{modelo}: N medido diferente do N da trava"
            assert int(medicao.resultados[modelo].matriz.to_numpy().sum()) == n, f"{modelo}: a matriz não soma o N"
        mudanca = medicao.mudancas[config.MODELO_PERSISTENCIA]
        assert mudanca.acerto_igual == 1.0 and mudanca.acerto_muda == 0.0, "a persistência não é o status_atual"
        ic = medicao.ic.iloc[0]
        pontual = medicao.resultados[config.MODELO_FLORESTA].f1_macro - medicao.resultados[config.MODELO_PERSISTENCIA].f1_macro
        assert abs(ic["diferenca_f1"] - pontual) <= config.TOLERANCIA_METRICA, "a diferença do IC não é a medida"
        assert ic["ic_inferior"] <= ic["ic_superior"], "limites do IC trocados"
        assert ic["fluxos"] == lido.localizacao["fluxo_id"].nunique(), "o IC não usou os fluxos do bloco"

    # ----------------------------------------------------------------------------------------------------------------
    # Entrada: escolha, SHA-256 e o pacote do modelo
    # ----------------------------------------------------------------------------------------------------------------
    def _carregar_modelo(self) -> tuple[RandomForestClassifier, dict, str]:
        escolha = self._ler_escolha()
        sha_modelo = _sha256(config.ARQUIVO_MODELO_FINAL)
        self._exigir_sha_do_leia_me(sha_modelo)  # antes de abrir: o .joblib é um pickle
        modelo = self._conferir_pacote(joblib.load(config.ARQUIVO_MODELO_FINAL), escolha)
        return modelo, escolha, sha_modelo

    @staticmethod
    def _conferir_carimbo(carimbo: Path, escolha: dict, sha_modelo: str) -> None:
        """O carimbo tem de bater com o modelo, a escolha e o código de medição de agora."""
        esperado = {
            "modelo": escolha["modelo"],
            "sha256_modelo": sha_modelo,
            "sha256_escolha": _sha256(config.ARQUIVO_ESCOLHA),
            "sha256_codigo": _hashes_do_codigo(),
        }
        conferir_carimbo(carimbo, esperado)

    @staticmethod
    def _ler_escolha() -> dict:
        necessarios = (config.ARQUIVO_ESCOLHA, config.ARQUIVO_LEIA_ME, config.ARQUIVO_MODELO_FINAL,
                       config.ARQUIVO_COMPARACAO_MODELOS, config.ARQUIVO_MATRIZ_COMPARACAO, config.ARQUIVO_IC_PAREADO)
        faltando = [str(arquivo) for arquivo in necessarios if not arquivo.exists()]
        if faltando:
            raise SystemExit(
                f"Não encontrei {', '.join(faltando)}.\n"
                "Rode antes: uv run python -m preditor exportar (que precisa do comparar antes)"
            )
        return json.loads(config.ARQUIVO_ESCOLHA.read_text(encoding="utf-8"))

    @staticmethod
    def _exigir_sha_do_leia_me(sha_modelo: str) -> None:
        """O arquivo medido é o que a exportação gravou: o SHA-256 atual tem de bater com a tabela do LEIA-ME."""
        for linha in config.ARQUIVO_LEIA_ME.read_text(encoding="utf-8").splitlines():
            if linha.startswith(f"| `{config.ARQUIVO_MODELO_FINAL.name}`"):
                achado = re.search(r"`([0-9a-f]{64})`", linha)
                assert achado is not None, "a linha do modelo no LEIA-ME não tem um SHA-256"
                gravado = achado.group(1)
                if gravado != sha_modelo:
                    raise SystemExit(
                        f"{config.ARQUIVO_MODELO_FINAL.name} mudou desde a exportação: SHA-256 {sha_modelo}, "
                        f"e o LEIA-ME tem {gravado}.\nNada foi lido. Refaça a exportação (preditor exportar) e rode o ensaio."
                    )
                return
        raise SystemExit(f"O LEIA-ME não tem a linha de {config.ARQUIVO_MODELO_FINAL.name}: não dá para conferir o SHA-256.")

    @staticmethod
    def _conferir_pacote(pacote: dict, escolha: dict):
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

    # ----------------------------------------------------------------------------------------------------------------
    # Casos concretos e fluxos
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _casos(bloco: BlocoLido, previsto: pd.Series) -> list[ErroConcreto]:
        """Um caso para cada `CASOS_TESTE`, com `Avaliacao._escolher` (o mesmo critério da validação) e conferência por laço."""
        # `_escolher` lê só colunas de localização, `z_robusto`, `verdadeiro`, `previsto` e `status_atual`. As 8 colunas da
        # árvore bastam: as duas novas (min5_z, media5_z) não entram no critério dos casos.
        quadro = pd.concat([bloco.localizacao, bloco.X[config.COLUNAS_ARVORE]], axis=1)
        quadro["status_atual"] = bloco.status_atual
        quadro["verdadeiro"] = bloco.y
        quadro["previsto"] = previsto
        casos = []
        for caso in CASOS_TESTE:
            erro = Avaliacao._escolher(quadro, caso, bloco.mediana_das_medianas)
            Avaliacao._verificar_erro(erro, quadro, bloco.mediana_das_medianas)
            casos.append(erro)
        return casos

    @staticmethod
    def _contar_fluxos(validacao: BlocoLido, teste: BlocoLido | None) -> dict:
        """Contagem de fluxos por código. O teste entra só na abertura (ler o `fluxo_id` dele é a abertura)."""
        baseline = pd.read_parquet(config.ARQUIVO_BASELINE)
        com_baseline = set(baseline.loc[~baseline["baseline_insuficiente"], "fluxo_id"])
        insuficientes = set(baseline.loc[baseline["baseline_insuficiente"], "fluxo_id"])
        # 81 no baseline, 2 insuficientes: 79 com baseline suficiente (a mesma conta de `dados_teste._medianas`).
        assert len(com_baseline) == config.FLUXOS_BASELINE - config.FLUXOS_INSUFICIENTES, (
            f"fluxos com baseline suficiente: {len(com_baseline)}"
        )
        assert len(insuficientes) == config.FLUXOS_INSUFICIENTES, f"fluxos insuficientes: {len(insuficientes)}"
        treino = set(DadosTeste(config.BLOCO_TREINO).carregar().localizacao["fluxo_id"])
        ids_validacao = set(validacao.localizacao["fluxo_id"])
        assert ids_validacao <= com_baseline, "a validação tem fluxo sem baseline suficiente"
        contagem = {
            "com_baseline": len(com_baseline),
            "no_treino": len(com_baseline & treino),
            "na_validacao": len(com_baseline & ids_validacao),
            "com_baseline_fora_do_treino": len(com_baseline - treino),
        }
        if teste is None:
            return contagem
        ids_teste = set(teste.localizacao["fluxo_id"])
        assert ids_teste <= com_baseline, "o teste tem fluxo sem baseline suficiente"
        nos_tres = treino | ids_validacao | ids_teste
        # Os três blocos juntos cobrem exatamente os fluxos com baseline suficiente; os insuficientes não aparecem em nenhum.
        assert nos_tres == com_baseline, f"os blocos cobrem {len(nos_tres)} fluxos, e o baseline suficiente tem {len(com_baseline)}"
        assert not (insuficientes & nos_tres), "fluxo com baseline insuficiente apareceu no dataset rotulado"
        contagem.update({
            "no_teste": len(com_baseline & ids_teste),
            "nos_tres_blocos": len(nos_tres),
            "insuficientes_fora_do_dataset": len(insuficientes - nos_tres),
        })
        return contagem

    # ----------------------------------------------------------------------------------------------------------------
    # Conferência com o que o `comparar` gravou (só o ensaio)
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _conferir_com_csv(comparacao: pd.DataFrame, resultados: dict, mudancas: dict, ic: pd.DataFrame,
                          y: pd.Series) -> None:
        """Os números medidos agora = os de `comparacao_modelos.csv`, `matriz_comparacao.csv` e `ic_pareado.csv`."""
        casa = 10**-config.CASAS_CSV  # o CSV arredonda: uma unidade da última casa de folga
        gravada = pd.read_csv(config.ARQUIVO_COMPARACAO_MODELOS).set_index("modelo")
        for modelo in (config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA):
            agora = comparacao.set_index("modelo").loc[modelo]
            for coluna in METRICAS_COMPARADAS:
                esperado = gravada.loc[modelo, coluna]
                assert abs(float(agora[coluna]) - float(esperado)) <= casa, (
                    f"{modelo}: {coluna} = {agora[coluna]} agora, e {esperado} em comparacao_modelos.csv"
                )
        # A persistência é "o futuro repete o agora": acerta tudo quando o futuro é igual e nada quando muda.
        assert mudancas[config.MODELO_PERSISTENCIA].acerto_igual == 1.0
        assert mudancas[config.MODELO_PERSISTENCIA].acerto_muda == 0.0

        # Matriz: inteiros exatos, nas duas linhas, e a soma é o N da validação.
        gravada_matriz = pd.read_csv(config.ARQUIVO_MATRIZ_COMPARACAO)
        colunas = [f"previsto_{classe}" for classe in config.CLASSES]
        for modelo in (config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA):
            igual = Avaliacao.quadro_matriz(modelo, resultados[modelo])
            da_gravada = gravada_matriz[gravada_matriz["modelo"] == modelo].reset_index(drop=True)
            assert igual[colunas].to_numpy().tolist() == da_gravada[colunas].to_numpy().tolist(), (
                f"{modelo}: matriz diferente de matriz_comparacao.csv"
            )
            assert int(igual[colunas].to_numpy().sum()) == len(y), f"{modelo}: a matriz não soma o N da validação"

        # IC: a linha (random_forest, persistencia) tem de sair igual; é a prova de que o conjunto de fluxos é o mesmo.
        gravado_ic = pd.read_csv(config.ARQUIVO_IC_PAREADO)
        linha = gravado_ic[(gravado_ic["modelo"] == config.MODELO_FLORESTA)
                           & (gravado_ic["referencia"] == config.MODELO_PERSISTENCIA)].iloc[0]
        agora_ic = ic.iloc[0]
        for coluna in ("diferenca_f1", "ic_inferior", "ic_superior"):
            assert abs(float(agora_ic[coluna]) - float(linha[coluna])) <= casa, f"IC: {coluna} diferente do ic_pareado.csv"
        assert bool(agora_ic["exclui_zero"]) == bool(linha["exclui_zero"]), "IC: exclui_zero diferente do ic_pareado.csv"
        assert int(linha["fluxos"]) == int(agora_ic["fluxos"]), "IC: número de fluxos diferente do ic_pareado.csv"

    # ----------------------------------------------------------------------------------------------------------------
    # Resultado da abertura: montagem, gravação e releitura
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _resultado(bloco_nome: str, sha_modelo: str, medicao: Medicao, n: int, fluxos: dict, inicio: str) -> dict:
        """O `resultado.json`: o que foi medido no bloco, os números da validação ao lado e a declaração pela regra."""
        ic = medicao.ic.iloc[0]
        declaracao = DECLARACAO_PREDITOR if ic["ic_inferior"] > 0 else DECLARACAO_DETECTOR  # só o limite inferior
        validacao_csv, distribuicao_validacao = _validacao_do_comparar()
        medido = {
            modelo: _para_json(medicao.comparacao.set_index("modelo").loc[modelo, list(METRICAS_COMPARADAS)])
            for modelo in (config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA)
        }
        distribuicao_medida = {
            classe: int(medicao.resultados[config.MODELO_FLORESTA].matriz.loc[classe].sum()) for classe in config.CLASSES
        }
        ensaio = bloco_nome != config.BLOCO_TESTE
        return {
            "modelo": config.MODELO_FLORESTA,
            "bloco": bloco_nome,
            "rotulo": "ensaio" if ensaio else "teste",
            "aviso": (
                "Medido nas linhas da validação pelo caminho da abertura: é um ensaio, não o resultado do teste."
                if ensaio else "Resultado do teste único (Tarefa 5)."
            ),
            "sha256_modelo": sha_modelo,
            "sha256_escolha": _sha256(config.ARQUIVO_ESCOLHA),
            "n": n,
            "aberto_em": inicio,
            "montado_em": _agora(),
            "declaracao": declaracao,
            "regra_declaracao": REGRA_DECLARACAO,
            "ic_ganho": {
                "diferenca_f1": round(float(ic["diferenca_f1"]), config.CASAS_CSV),
                "ic_inferior": round(float(ic["ic_inferior"]), config.CASAS_CSV),
                "ic_superior": round(float(ic["ic_superior"]), config.CASAS_CSV),
                "exclui_zero": bool(ic["exclui_zero"]),
                "reamostras": int(ic["reamostras"]),
                "fluxos": int(ic["fluxos"]),
            },
            "medido": medido,
            "validacao_do_comparar": validacao_csv,
            "distribuicao_verdadeiro": {"medido": distribuicao_medida, "validacao": distribuicao_validacao},
            "fluxos": fluxos,
            "limitacao_fluxo_novo": _limitacao_fluxo_novo(fluxos),
        }

    @staticmethod
    def _gravar_saidas(saidas: Saidas, medicao: Medicao, resultado: dict) -> None:
        """Só depois de todas as checagens: as cinco saídas da abertura."""
        matriz = pd.concat([Avaliacao.quadro_matriz(m, r) for m, r in medicao.resultados.items()], ignore_index=True)
        matriz.to_csv(saidas.matriz, index=False)
        sem_regioes = pd.DataFrame(columns=["regiao", "n", "f1_macro", "acuracia"])  # o teste não tem região (T4)
        metricas = pd.concat(
            [Avaliacao.quadro_metricas(m, r) for m, r in medicao.resultados.items()]
            + [Avaliacao.quadro_extras(m, medicao.mudancas[m], sem_regioes) for m in medicao.resultados],
            ignore_index=True,
        )
        metricas.to_csv(saidas.metricas, index=False)
        medicao.ic.round(config.CASAS_CSV).to_csv(saidas.ic, index=False)
        saidas.casos.write_text("\n".join(_linhas_casos(medicao.casos, medicao.mediana)) + "\n", encoding="utf-8")
        saidas.resultado.write_text(_json(resultado), encoding="utf-8")

    @staticmethod
    def _verificar_disco(saidas: Saidas, medicao: Medicao, resultado: dict, n: int) -> None:
        """Relê o que foi gravado e confere com a memória, por outro caminho (CSV → matriz → F1 recalculado)."""
        casa = 10**-config.CASAS_CSV
        for arquivo in (saidas.matriz, saidas.metricas, saidas.ic, saidas.casos, saidas.resultado):
            assert arquivo.exists() and arquivo.stat().st_size > 0, f"{arquivo.name} não foi gravado"

        colunas = [f"previsto_{classe}" for classe in config.CLASSES]
        matriz = pd.read_csv(saidas.matriz)
        for modelo in (config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA):
            assert int(matriz[matriz["modelo"] == modelo][colunas].to_numpy().sum()) == n, f"{modelo}: a matriz gravada não soma o N"
        # O F1 macro da floresta é refeito da matriz GRAVADA, com a conta de `comparacao.py` (não da memória).
        da_matriz = matriz[matriz["modelo"] == config.MODELO_FLORESTA][colunas].to_numpy(dtype=float)
        f1_refeito = float(f1_macro_das_matrizes(da_matriz[None])[0])
        assert abs(f1_refeito - medicao.resultados[config.MODELO_FLORESTA].f1_macro) <= config.TOLERANCIA_METRICA, (
            "o F1 refeito da matriz gravada não bate com o medido"
        )

        metricas = pd.read_csv(saidas.metricas)
        gravado = metricas[(metricas["modelo"] == config.MODELO_FLORESTA) & (metricas["metrica"] == "f1_macro")]["valor"].iloc[0]
        assert abs(gravado - medicao.resultados[config.MODELO_FLORESTA].f1_macro) <= casa, "F1 macro gravado diferente"

        ic = pd.read_csv(saidas.ic).iloc[0]
        agora = medicao.ic.iloc[0]
        assert abs(ic["ic_inferior"] - agora["ic_inferior"]) <= casa and abs(ic["ic_superior"] - agora["ic_superior"]) <= casa, (
            "IC gravado diferente do calculado"
        )

        relido = json.loads(saidas.resultado.read_text(encoding="utf-8"))
        assert relido == json.loads(_json(resultado)), "resultado.json diferente do montado"
        texto_casos = saidas.casos.read_text(encoding="utf-8")
        for erro in medicao.casos:
            if erro.linha is not None:
                assert str(erro.linha["fluxo_id"]) in texto_casos, f"o caso {erro.caso.titulo!r} não está em casos_teste.txt"

    # ----------------------------------------------------------------------------------------------------------------
    # Impressão e carimbo
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _imprimir(medicao: Medicao, fluxos: dict, escolha: dict, rotulo: str, n: int) -> None:
        print(f"\nN do bloco {rotulo} = {n} medições (as mesmas para o modelo e para a persistência).")
        print("Números medidos (F1 macro, F1 por classe, recall, transições):")
        print(f"  {'modelo':<19}{'F1 macro':>9}{'F1 OK':>8}{'F1 RISCO':>10}{'F1 FALHA':>10}{'rec FALHA':>10}"
              f"{'rec RISCO':>10}{'OK→FALHA':>10}{'FALHA→OK':>10}")
        for linha in medicao.comparacao.itertuples(index=False):
            print(f"  {linha.modelo:<19}{linha.f1_macro:>9.4f}{linha.f1_OK:>8.4f}{linha.f1_RISCO:>10.4f}"
                  f"{linha.f1_FALHA:>10.4f}{linha.recall_FALHA:>10.4f}{linha.recall_RISCO:>10.4f}"
                  f"{linha.acerto_OK_para_FALHA:>10.1%}{linha.acerto_FALHA_para_OK:>10.1%}")
        print("  (OK→FALHA e FALHA→OK são acertos nas transições agora → futuro.)")

        print("\nMatriz da Random Forest, em contagem (linha = verdadeiro, coluna = previsto):")
        print(f"  {'verdadeiro':<12}" + "".join(f"{'previsto ' + classe:>16}" for classe in config.CLASSES))
        for classe, linha in medicao.resultados[config.MODELO_FLORESTA].matriz.iterrows():
            print(f"  {classe:<12}" + "".join(f"{int(valor):>16}" for valor in linha))

        ganho = medicao.ic.iloc[0]
        print(f"\nIC 95 % pareado por fluxo do ganho de F1 macro sobre a persistência ({int(ganho['fluxos'])} fluxos):")
        print(f"  {ganho['diferenca_f1']:+.4f}  [{ganho['ic_inferior']:+.4f}; {ganho['ic_superior']:+.4f}]  "
              f"{'exclui o zero' if ganho['exclui_zero'] else 'contém o zero'}")

        print("\nDois casos concretos (fluxo_id e horário; primeiro acerto, depois erro):")
        for linha in _linhas_casos(medicao.casos, medicao.mediana):
            print(f"  {linha}")

        print("\nFluxos (contagem por código):")
        print("  " + "; ".join(f"{nome.replace('_', ' ')}: {valor}" for nome, valor in fluxos.items()))
        print(f"\nEscolha do comparar: {escolha['modelo']} (F1 macro {escolha['f1_macro_escolhido']:.4f}).")

    @staticmethod
    def _gravar_carimbo(sha_modelo: str, escolha: dict, n: int) -> None:
        """Grava `ensaio_ok.json` só com o ensaio inteiro verde. Sem data: duas execuções gravam o mesmo arquivo."""
        config.TESTE.mkdir(parents=True, exist_ok=True)
        carimbo = {
            "modelo": escolha["modelo"],
            "sha256_modelo": sha_modelo,
            "sha256_escolha": _sha256(config.ARQUIVO_ESCOLHA),
            "sha256_codigo": _hashes_do_codigo(),
            "n_validacao": n,
            "resultado": "ensaio ok: os números da validação batem com comparacao_modelos.csv, matriz_comparacao.csv e ic_pareado.csv",
        }
        config.ARQUIVO_ENSAIO_OK.write_text(_json(carimbo), encoding="utf-8")
        print(f"Gravado: {config.ARQUIVO_ENSAIO_OK}")


# --------------------------------------------------------------------------------------------------------------------
# Funções auxiliares
# --------------------------------------------------------------------------------------------------------------------
def _validacao_do_comparar() -> tuple[dict, dict]:
    """Os números da validação como estão em `comparacao_modelos.csv` e `matriz_comparacao.csv` (não são refeitos)."""
    comparacao = pd.read_csv(config.ARQUIVO_COMPARACAO_MODELOS).set_index("modelo")
    metricas = {
        modelo: _para_json(comparacao.loc[modelo, list(METRICAS_COMPARADAS)])
        for modelo in (config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA)
    }
    matriz = pd.read_csv(config.ARQUIVO_MATRIZ_COMPARACAO)
    colunas = [f"previsto_{classe}" for classe in config.CLASSES]
    da_floresta = matriz[matriz["modelo"] == config.MODELO_FLORESTA].set_index("verdadeiro")[colunas]
    # A soma de cada linha é quantas medições da validação são daquela classe verdadeira (só contagem).
    contagem = {classe: int(da_floresta.loc[classe].sum()) for classe in config.CLASSES}
    return metricas, contagem


def _limitacao_fluxo_novo(fluxos: dict) -> str:
    """A limitação do fluxo não visto, com a contagem que a sustenta (SPEC-teste-final.md, "Fluxo que o modelo não viu")."""
    fora = fluxos["com_baseline_fora_do_treino"]
    if fora == 0:
        return (
            f"Nenhum fluxo com baseline suficiente ficou fora do treino: os {fluxos['com_baseline']} fluxos com baseline "
            "aparecem no treino, na validação e no teste (contagem por código). Não há fluxo não visto para medir. O teste "
            "mede os mesmos fluxos que o modelo treinou: não responde se o modelo generaliza para um fluxo novo. "
            "Limitação declarada. Os 2 fluxos com baseline insuficiente não estão no dataset rotulado; o 82º fluxo do Silver "
            "não tem ficha de baseline."
        )
    return (
        f"{fora} fluxo(s) com baseline suficiente ficaram fora do treino: o teste mede também esses fluxos. "
        "A contagem é a da tabela de fluxos; a limitação de fluxo novo muda com este número."
    )


def _linhas_casos(casos: list, mediana: float) -> list[str]:
    """Os dois casos em texto, com fluxo_id, horário e critério (o mesmo texto vai para o terminal e para casos_teste.txt)."""
    linhas = []
    for numero, erro in enumerate(casos, start=1):
        linhas.append(f"Caso {numero}: {erro.caso.titulo}")
        linhas.append(f"  critério: {erro.caso.descricao(mediana)}")
        if erro.linha is None:
            linhas.append("  não apareceu no bloco (nenhuma linha atende ao critério).")
            continue
        linha = erro.linha
        linhas.append(f"  {erro.candidatos} linhas atendem ao critério; esta é a primeira da lista ordenada.")
        linhas.append(f"  fluxo_id: {linha['fluxo_id']}   t: {linha['t']}   rtt: {linha['rtt']:.2f} ms")
        linhas.append(
            f"  verdadeiro: {linha['verdadeiro']}   previsto: {linha['previsto']}   status_atual: {linha['status_atual']}"
        )
    return linhas


def _para_json(linha: pd.Series) -> dict:
    """Uma linha de métricas como números comuns do Python: inteiros para as contagens, floats para o resto."""
    return {nome: (int(valor) if nome.startswith("n_") else round(float(valor), config.CASAS_CSV))
            for nome, valor in linha.items()}


def _json(conteudo: dict) -> str:
    return json.dumps(conteudo, indent=2, ensure_ascii=False) + "\n"


def _agora() -> str:
    """Data e hora local com o deslocamento de fuso, até o segundo (a trava e o resultado; o carimbo não tem data)."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _hashes_do_codigo() -> dict[str, str]:
    return {arquivo.name: _sha256(arquivo) for arquivo in CODIGO_DE_MEDICAO}


def _sha256(arquivo: Path) -> str:
    """SHA-256 do arquivo inteiro, como o `shasum -a 256` de macOS e o `sha256sum` de Linux."""
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()
