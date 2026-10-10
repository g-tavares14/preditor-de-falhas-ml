"""Orquestra a comparação Random Forest × XGBoost × árvore (SPEC-comparacao-modelos.md): mede, escolhe, verifica e grava.

Roda sem Spark e sem Java, como `arvore`, `ajuste` e `replay`. Mede cinco linhas nas MESMAS linhas da validação:
persistência, árvore da Tarefa 3 (refeita), árvore ajustada com peso, Random Forest e XGBoost. Só grava depois que
todas as checagens passam, e relê do disco o que gravou. Escreve só em `data/modelo/comparacao/`: não toca as saídas
do `arvore`, do `ajuste` nem do `replay`, e o teste continua fechado.
"""

import json
import time

import numpy as np
import pandas as pd

from preditor import config
from preditor.modelo.ajuste import ArvoreAjustada
from preditor.modelo.arvore import Arvore
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.boosting import COMBINACAO as COMBINACAO_BOOSTING
from preditor.modelo.boosting import ORDEM_SIMPLICIDADE as ORDEM_BOOSTING
from preditor.modelo.boosting import Boosting
from preditor.modelo.comparacao import escolher_por_regra, ic_pareado, quadro_comparacao, quadro_importancias
from preditor.modelo.dados import DadosModelo
from preditor.modelo.floresta import COMBINACAO as COMBINACAO_FLORESTA
from preditor.modelo.floresta import ORDEM_SIMPLICIDADE as ORDEM_FLORESTA
from preditor.modelo.floresta import Floresta

# Pares do IC pareado (a − b): o ganho de cada família sobre a árvore ajustada e sobre a persistência, e a diferença
# entre as duas famílias. Não decidem nada: só dizem se a diferença tem prova de ser maior que o ruído.
PARES_IC = [
    (config.MODELO_FLORESTA, config.MODELO_AJUSTADA),
    (config.MODELO_BOOSTING, config.MODELO_AJUSTADA),
    (config.MODELO_FLORESTA, config.MODELO_PERSISTENCIA),
    (config.MODELO_BOOSTING, config.MODELO_PERSISTENCIA),
    (config.MODELO_BOOSTING, config.MODELO_FLORESTA),
]


class ExecucaoComparacao:
    def executar(self) -> None:
        self._exigir_saidas_anteriores()
        # Sem o Gold (ou com um Gold sem as colunas novas), `DadosModelo` diz qual comando rodar antes.
        dados = DadosModelo().carregar()
        validacao = config.BLOCO_VALIDACAO
        verdadeiro = dados.y[validacao]
        X_validacao = dados.x_ajustado(validacao)
        self._imprimir_dados(dados)

        # 1. Treino de cada modelo (só com o bloco de treino) e medida dos tempos. A árvore da Tarefa 3 e a ajustada
        # são refeitas aqui com a mesma semente, para serem medidas ao lado das duas famílias novas.
        tempos = []  # (modelo, etapa, combinação, segundos): vão para `tempos.csv`, fora da checagem de arquivos iguais
        inicio = time.perf_counter()
        tarefa_3 = Arvore().buscar(dados)
        tempos.append((config.MODELO_ARVORE, "busca inteira", "28 árvores", time.perf_counter() - inicio))
        inicio = time.perf_counter()
        ajustada = ArvoreAjustada(config.MODELO_AJUSTADA, config.VARIANTES_AJUSTE[config.MODELO_AJUSTADA]).buscar(dados)
        tempos.append((config.MODELO_AJUSTADA, "busca inteira", "56 árvores", time.perf_counter() - inicio))
        inicio = time.perf_counter()
        floresta = Floresta().buscar(dados)
        tempos.append((config.MODELO_FLORESTA, "busca inteira", f"{len(floresta.busca)} florestas", time.perf_counter() - inicio))
        inicio = time.perf_counter()
        boosting = Boosting().buscar(dados)
        tempos.append((config.MODELO_BOOSTING, "busca inteira", f"{len(boosting.busca)} modelos", time.perf_counter() - inicio))
        tempos += self._tempos_de_cada_combinacao(floresta, boosting)

        # Previsão de cada modelo na validação (o X de cada um: 8 colunas na árvore da Tarefa 3, 10 nas outras).
        previstos = {
            config.MODELO_PERSISTENCIA: dados.status_atual_validacao,
            config.MODELO_ARVORE: tarefa_3.prever(dados.X[validacao]),
            config.MODELO_AJUSTADA: ajustada.prever_bloco(dados, validacao),
            config.MODELO_FLORESTA: floresta.prever(X_validacao),
            config.MODELO_BOOSTING: boosting.prever(X_validacao),
        }
        tempos += [
            (config.MODELO_ARVORE, f"previsão da validação (mediana de {config.REPETICOES_PREVISAO})", "",
             self._mediana_previsao(lambda: tarefa_3.prever(dados.X[validacao]))),
            (config.MODELO_AJUSTADA, f"previsão da validação (mediana de {config.REPETICOES_PREVISAO})", "",
             self._mediana_previsao(lambda: ajustada.prever_bloco(dados, validacao))),
            (config.MODELO_FLORESTA, f"previsão da validação (mediana de {config.REPETICOES_PREVISAO})", "",
             self._mediana_previsao(lambda: floresta.prever(X_validacao))),
            (config.MODELO_BOOSTING, f"previsão da validação (mediana de {config.REPETICOES_PREVISAO})", "",
             self._mediana_previsao(lambda: boosting.prever(X_validacao))),
        ]

        # 2. As mesmas contas para as cinco linhas: matriz, F1 por classe, transições e o tamanho de cada uma.
        resultados = {m: Avaliacao.medir(verdadeiro, p, bloco=validacao) for m, p in previstos.items()}
        mudancas = {
            m: Avaliacao.quando_muda(verdadeiro, p, dados.status_atual_validacao, bloco=validacao) for m, p in previstos.items()
        }
        tamanhos = self._tamanhos(tarefa_3, ajustada, floresta, boosting)

        # 3. Regra entre famílias (SPEC, "Regra de escolha", item 2): só entram as três candidatas, e a ordem de
        # simplicidade é a da spec. A persistência e a árvore da Tarefa 3 são só referência.
        familias = pd.DataFrame(
            {
                "modelo": config.ORDEM_FAMILIAS,
                "posicao": range(1, len(config.ORDEM_FAMILIAS) + 1),
                "f1_macro_validacao": [resultados[m].f1_macro for m in config.ORDEM_FAMILIAS],
            }
        )
        escolhido = str(familias.loc[escolher_por_regra(familias, [("posicao", True)]), "modelo"])
        f1_persistencia = resultados[config.MODELO_PERSISTENCIA].f1_macro
        supera_persistencia = resultados[escolhido].f1_macro > f1_persistencia

        # 4. IC pareado por fluxo (não decide): os mesmos fluxos reamostrados para todos os modelos.
        ic, f1_pontual = ic_pareado(verdadeiro, previstos, dados.localizacao_validacao["fluxo_id"], PARES_IC)

        # 5. O que vai para os arquivos: a comparação, a matriz, as importâncias e a escolha.
        comparacao = quadro_comparacao(resultados, mudancas, tamanhos, escolhido)
        matriz = pd.concat([Avaliacao.quadro_matriz(m, r) for m, r in resultados.items()], ignore_index=True)
        importancias = quadro_importancias(self._importancias(ajustada, floresta, boosting))
        escolha = self._escolha(escolhido, familias, resultados, supera_persistencia, floresta, boosting, ajustada)
        tempos_quadro = pd.DataFrame(tempos, columns=["modelo", "etapa", "combinacao", "segundos"]).round(4)

        # Tudo é conferido ANTES de gravar: uma checagem que falha não deixa arquivo novo.
        self._verificar_modelos(dados, tarefa_3, ajustada, floresta, boosting)
        self._verificar_medidas(dados, previstos, resultados, mudancas, f1_pontual, verdadeiro)
        self._verificar_escolha(familias, escolhido, resultados, supera_persistencia)
        self._verificar_ic(ic, resultados, verdadeiro, previstos, dados.localizacao_validacao["fluxo_id"])
        self._verificar_arquivos_anteriores(tarefa_3, ajustada, resultados)
        self._verificar_teste(dados, verdadeiro)
        self._imprimir_resultados(comparacao, ic, tempos_quadro, escolha, dados)

        self._gravar(floresta, boosting, comparacao, matriz, ic, importancias, escolha, tempos_quadro)
        self._verificar_disco(dados, resultados, floresta, boosting, escolha, ic)
        print("\nComparação: todas as checagens passaram. O teste continua fechado.")

    # ----------------------------------------------------------------------------------------------------------------
    # Entrada e saídas anteriores
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _exigir_saidas_anteriores() -> None:
        """A comparação refaz a Tarefa 3 e a ajustada e confere as duas com o que o `arvore` e o `ajuste` gravaram."""
        necessarios = (
            config.ARQUIVO_ARVORE, config.ARQUIVO_METRICAS, config.ARQUIVO_ARVORE_AJUSTADA,
            config.ARQUIVO_METRICAS_AJUSTE, config.ARQUIVO_BUSCA_AJUSTE,
        )
        faltando = [str(arquivo) for arquivo in necessarios if not arquivo.exists()]
        if faltando:
            raise SystemExit(
                f"Não encontrei {', '.join(faltando)}.\n"
                "Rode antes: uv run python -m preditor arvore, e depois uv run python -m preditor ajuste"
            )

    @staticmethod
    def _imprimir_dados(dados: DadosModelo) -> None:
        print("Comparação de modelos (SPEC-comparacao-modelos.md): as cinco linhas na validação.")
        print(f"  {'treino':<10} N = {dados.resumo[config.BLOCO_TREINO]['n']:>6}")
        print(f"  {config.BLOCO_VALIDACAO:<10} N = {dados.resumo[config.BLOCO_VALIDACAO]['n']:>6} (as mesmas linhas para as cinco)")
        print(f"  {config.BLOCO_TESTE:<10} N = {dados.n_teste:>6} | fechado até a Tarefa 5 (nada dele é lido nem medido)")

    # ----------------------------------------------------------------------------------------------------------------
    # Tempos, tamanhos e importâncias
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _tempos_de_cada_combinacao(floresta: Floresta, boosting: Boosting) -> list[tuple[str, str, str, float]]:
        """Um tempo de treino por combinação da grade (cada `fit`, sem a medição de F1)."""
        linhas = []
        for linha, segundos in zip(floresta.busca.itertuples(index=False), floresta.tempos):
            combinacao = f"n={linha.n_estimators} prof={linha.max_depth} folha={linha.min_samples_leaf}"
            linhas.append((config.MODELO_FLORESTA, "treino de uma combinação", combinacao, float(segundos)))
        for linha, segundos in zip(boosting.busca.itertuples(index=False), boosting.tempos):
            combinacao = f"n={linha.n_estimators} taxa={linha.learning_rate} prof={linha.max_depth}"
            linhas.append((config.MODELO_BOOSTING, "treino de uma combinação", combinacao, float(segundos)))
        return linhas

    @staticmethod
    def _mediana_previsao(prever) -> float:
        """Mediana de `REPETICOES_PREVISAO` previsões na validação: uma medição só varia com a carga da máquina."""
        medidas = []
        for _ in range(config.REPETICOES_PREVISAO):
            inicio = time.perf_counter()
            prever()
            medidas.append(time.perf_counter() - inicio)
        return float(np.median(medidas))

    @staticmethod
    def _tamanhos(tarefa_3: Arvore, ajustada: ArvoreAjustada, floresta: Floresta, boosting: Boosting) -> dict:
        """(árvores, folhas, nós) de cada modelo. A persistência não é árvore: fica vazia."""
        escolhida_rf = floresta.busca.loc[floresta.posicao_escolhida]
        escolhida_xgb = boosting.busca.loc[boosting.posicao_escolhida]
        return {
            config.MODELO_PERSISTENCIA: (None, None, None),
            config.MODELO_ARVORE: (1, int(tarefa_3.modelo.tree_.n_leaves), int(tarefa_3.modelo.tree_.node_count)),
            config.MODELO_AJUSTADA: (1, int(ajustada.modelo.tree_.n_leaves), int(ajustada.modelo.tree_.node_count)),
            config.MODELO_FLORESTA: (
                int(escolhida_rf["n_estimators"]), int(escolhida_rf["folhas_total"]), int(escolhida_rf["nos_total"]),
            ),
            config.MODELO_BOOSTING: (
                int(escolhida_xgb["arvores"]), int(escolhida_xgb["folhas_total"]), int(escolhida_xgb["nos_total"]),
            ),
        }

    @staticmethod
    def _importancias(ajustada: ArvoreAjustada, floresta: Floresta, boosting: Boosting) -> dict[str, pd.Series]:
        """Importância de cada coluna do X (soma 1 em cada modelo) para o relatório."""
        return {
            config.MODELO_AJUSTADA: pd.Series(
                ajustada.modelo.feature_importances_, index=DadosModelo.colunas_ajustadas()
            ),
            config.MODELO_FLORESTA: pd.Series(
                floresta.modelo.feature_importances_, index=list(floresta.modelo.feature_names_in_)
            ),
            config.MODELO_BOOSTING: pd.Series(
                boosting.modelo.feature_importances_, index=list(boosting.modelo.feature_names_in_)
            ),
        }

    # ----------------------------------------------------------------------------------------------------------------
    # Escolha e arquivo de escolha
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _parametros(modelo: str, ajustada: ArvoreAjustada, floresta: Floresta, boosting: Boosting) -> dict:
        """Os hiperparâmetros do modelo escolhido, como vão para `escolha.json` (valores comuns do JSON)."""
        if modelo == config.MODELO_FLORESTA:
            return {
                "n_estimators": int(floresta.modelo.n_estimators),
                "max_depth": int(floresta.modelo.max_depth),
                "min_samples_leaf": int(floresta.modelo.min_samples_leaf),
                "max_features": floresta.modelo.max_features,
                "criterion": floresta.modelo.criterion,
                "class_weight": floresta.modelo.class_weight,
                "semente": config.SEMENTE,
            }
        if modelo == config.MODELO_BOOSTING:
            return {
                "n_estimators": int(boosting.modelo.n_estimators),
                "learning_rate": float(boosting.modelo.learning_rate),
                "max_depth": int(boosting.modelo.max_depth),
                "tree_method": config.TREE_METHOD_BOOSTING,
                "class_weight_por_linha": config.VARIANTES_AJUSTE[config.MODELO_AJUSTADA],
                "semente": config.SEMENTE,
            }
        return ajustada.descricao()

    def _escolha(
        self, escolhido, familias, resultados, supera_persistencia, floresta, boosting, ajustada
    ) -> dict:
        """O que vai para `escolha.json`: o modelo, os parâmetros, as candidatas e o motivo, em texto."""
        melhor = familias.loc[familias["f1_macro_validacao"].idxmax(), "modelo"]
        limite = familias["f1_macro_validacao"].max() - config.TOLERANCIA_ESCOLHA
        candidatas = []
        for linha in familias.itertuples(index=False):
            candidatas.append(
                {
                    "modelo": linha.modelo,
                    "f1_macro_validacao": round(float(linha.f1_macro_validacao), config.CASAS_CSV),
                    "dentro_da_tolerancia": bool(linha.f1_macro_validacao >= limite),
                }
            )
        dentro = [c["modelo"] for c in candidatas if c["dentro_da_tolerancia"]]
        f1_escolhido = resultados[escolhido].f1_macro
        f1_persistencia = resultados[config.MODELO_PERSISTENCIA].f1_macro
        supera = "supera" if supera_persistencia else "NÃO supera"
        motivo = (
            f"O maior F1 macro entre as candidatas é de {melhor} ({resultados[melhor].f1_macro:.4f}). "
            f"Ficaram dentro da tolerância de {config.TOLERANCIA_ESCOLHA:g}: {', '.join(dentro)}. "
            f"Entre elas, a mais simples na ordem {', '.join(config.ORDEM_FAMILIAS)} é {escolhido}, "
            f"com F1 macro {f1_escolhido:.4f}. Ele {supera} a persistência ({f1_persistencia:.4f})."
        )
        return {
            "modelo": escolhido,
            "parametros": self._parametros(escolhido, ajustada, floresta, boosting),
            "regra": "entre as candidatas, as a até tolerancia_escolha do maior F1 macro da validação; vence a mais simples",
            "tolerancia_escolha": config.TOLERANCIA_ESCOLHA,
            "semente": config.SEMENTE,
            "ordem_familias": list(config.ORDEM_FAMILIAS),
            "candidatas": candidatas,
            "f1_macro_escolhido": round(float(f1_escolhido), config.CASAS_CSV),
            "f1_macro_persistencia": round(float(f1_persistencia), config.CASAS_CSV),
            "supera_persistencia": bool(supera_persistencia),
            "motivo": motivo,
            "ic_pareado": "gravado em ic_pareado.csv; não decide a escolha",
        }

    # ----------------------------------------------------------------------------------------------------------------
    # Checagens (antes de gravar)
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _verificar_modelos(dados: DadosModelo, tarefa_3: Arvore, ajustada: ArvoreAjustada,
                           floresta: Floresta, boosting: Boosting) -> None:
        """As checagens de cada modelo (grade, colunas, regra, fit só no treino, mesma semente) valem de novo aqui."""
        tarefa_3.verificar(dados)
        ajustada.verificar(dados)
        floresta.verificar(dados)
        boosting.verificar(dados)
        # As 10 colunas da ajustada, a mesma ordem, nas duas famílias novas.
        colunas = DadosModelo.colunas_ajustadas()
        assert list(floresta.modelo.feature_names_in_) == colunas, "a Random Forest não foi treinada com as 10 colunas"
        assert list(boosting.modelo.feature_names_in_) == colunas, "o XGBoost não foi treinado com as 10 colunas"

    @staticmethod
    def _verificar_medidas(dados: DadosModelo, previstos: dict, resultados: dict, mudancas: dict,
                           f1_pontual: dict, verdadeiro: pd.Series) -> None:
        """As cinco linhas nas mesmas linhas da validação, com N igual e F1 do IC igual ao da `Avaliacao`."""
        n = dados.resumo[config.BLOCO_VALIDACAO]["n"]
        assert len(verdadeiro) == n, "o N da validação não bate com o resumo"
        assert config.MODELO_PERSISTENCIA in previstos, "falta a persistência"
        for modelo, previsto in previstos.items():
            assert previsto.index.equals(verdadeiro.index), f"{modelo}: previu outras linhas que não as da validação"
            assert resultados[modelo].n == n, f"{modelo}: N medido diferente do N da validação"
            assert set(previsto.unique()) <= set(config.CLASSES), f"{modelo}: previsão fora de OK/RISCO/FALHA"
        # O IC refez o F1 de cada modelo por outro caminho (matrizes somadas por fluxo): tem de bater com a Avaliacao.
        for modelo, valor in f1_pontual.items():
            assert abs(valor - resultados[modelo].f1_macro) <= config.TOLERANCIA_METRICA, (
                f"{modelo}: F1 do IC ({valor:.9f}) diferente do medido ({resultados[modelo].f1_macro:.9f})"
            )
        # A persistência é "o futuro repete o agora": acerta tudo quando o futuro é igual ao status_atual e nada quando muda.
        persistencia = mudancas[config.MODELO_PERSISTENCIA]
        assert persistencia.acerto_igual == 1.0 and persistencia.acerto_muda == 0.0, "a persistência não é o status_atual"

    @staticmethod
    def _verificar_escolha(familias: pd.DataFrame, escolhido: str, resultados: dict, supera: bool) -> None:
        """A regra entre famílias conferida por outro caminho (um laço, sem ordenar), e a persistência fora das candidatas."""
        assert set(familias["modelo"]) == set(config.ORDEM_FAMILIAS), "as candidatas não são as três famílias"
        assert config.MODELO_PERSISTENCIA not in familias["modelo"].to_list(), "a persistência não é candidata"
        assert config.MODELO_ARVORE not in familias["modelo"].to_list(), "a árvore da Tarefa 3 não é candidata"

        melhor = familias["f1_macro_validacao"].max()
        limite = melhor - config.TOLERANCIA_ESCOLHA
        linha_escolhida = familias[familias["modelo"] == escolhido].iloc[0]
        assert linha_escolhida["f1_macro_validacao"] >= limite, f"{escolhido} está fora da tolerância"
        # Nenhuma família MAIS SIMPLES que a escolhida (pela posição na ordem da spec) pode estar dentro da tolerância.
        for linha in familias.itertuples(index=False):
            if linha.posicao < linha_escolhida["posicao"]:
                assert linha.f1_macro_validacao < limite, f"{linha.modelo} é mais simples e está dentro da tolerância"
        # A escolhida tem o F1 que a `Avaliacao` mediu (a tabela de candidatas usa o mesmo número).
        assert abs(linha_escolhida["f1_macro_validacao"] - resultados[escolhido].f1_macro) <= config.TOLERANCIA_METRICA
        assert supera == (resultados[escolhido].f1_macro > resultados[config.MODELO_PERSISTENCIA].f1_macro), (
            "o campo 'supera a persistência' não bate com os F1"
        )

    @staticmethod
    def _verificar_ic(ic: pd.DataFrame, resultados: dict, verdadeiro: pd.Series,
                      previstos: dict, fluxos: pd.Series) -> None:
        """O IC: uma linha por par, limites na ordem, a diferença pontual certa, e a mesma saída numa segunda rodada."""
        assert len(ic) == len(PARES_IC), "o IC não tem uma linha por par"
        for linha in ic.itertuples(index=False):
            assert linha.ic_inferior <= linha.ic_superior, f"IC de {linha.modelo} − {linha.referencia} com limites trocados"
            pontual = resultados[linha.modelo].f1_macro - resultados[linha.referencia].f1_macro
            assert abs(linha.diferenca_f1 - pontual) <= config.TOLERANCIA_METRICA, "diferença pontual do IC errada"
            assert linha.exclui_zero == (linha.ic_inferior > 0 or linha.ic_superior < 0), "exclui_zero não bate com os limites"
            assert linha.reamostras == config.IC_REAMOSTRAS
            assert linha.fluxos == fluxos.nunique(), "o IC não usou todos os fluxos da validação"
        # Mesma semente = mesmo IC: uma segunda rodada, com as mesmas entradas, dá a mesma tabela.
        segunda, _ = ic_pareado(verdadeiro, previstos, fluxos, PARES_IC)
        assert segunda.equals(ic), "o IC mudou ao rodar de novo com a mesma semente"

    @staticmethod
    def _verificar_arquivos_anteriores(tarefa_3: Arvore, ajustada: ArvoreAjustada, resultados: dict) -> None:
        """A Tarefa 3 e a ajustada refeitas aqui são as que o `arvore` e o `ajuste` gravaram (mesmos parâmetros e F1)."""
        arvore_gravada = json.loads(config.ARQUIVO_ARVORE.read_text(encoding="utf-8"))
        assert tarefa_3.descricao() == arvore_gravada, "a árvore da Tarefa 3 refeita difere de arvore_oficial.json"
        ajustada_gravada = json.loads(config.ARQUIVO_ARVORE_AJUSTADA.read_text(encoding="utf-8"))
        assert ajustada.descricao() == ajustada_gravada, "a árvore ajustada refeita difere de arvore_ajustada.json"

        casa = 10**-config.CASAS_CSV
        metricas = pd.read_csv(config.ARQUIVO_METRICAS)
        f1_t3 = metricas[(metricas["modelo"] == config.MODELO_ARVORE) & (metricas["metrica"] == "f1_macro")]["valor"].iloc[0]
        assert abs(f1_t3 - resultados[config.MODELO_ARVORE].f1_macro) <= casa, "F1 da Tarefa 3 diferente de metricas_validacao.csv"
        f1_persistencia = metricas[(metricas["modelo"] == config.MODELO_PERSISTENCIA) & (metricas["metrica"] == "f1_macro")]["valor"].iloc[0]
        assert abs(f1_persistencia - resultados[config.MODELO_PERSISTENCIA].f1_macro) <= casa, "F1 da persistência diferente"
        metricas_ajuste = pd.read_csv(config.ARQUIVO_METRICAS_AJUSTE)
        f1_ajustada = metricas_ajuste[
            (metricas_ajuste["modelo"] == config.MODELO_AJUSTADA) & (metricas_ajuste["metrica"] == "f1_macro")
        ]["valor"].iloc[0]
        assert abs(f1_ajustada - resultados[config.MODELO_AJUSTADA].f1_macro) <= casa, "F1 da ajustada diferente de metricas_ajuste.csv"

    @staticmethod
    def _verificar_teste(dados: DadosModelo, verdadeiro: pd.Series) -> None:
        """O teste continua fechado: nenhuma linha dele no objeto de dados e a `Avaliacao` recusa medi-lo."""
        assert config.BLOCO_TESTE not in dados.X and config.BLOCO_TESTE not in dados.y, "o teste apareceu em DadosModelo"
        assert isinstance(dados.n_teste, int) and dados.n_teste > 0, "o N do teste deveria ser só um número"
        try:
            Avaliacao.medir(verdadeiro, verdadeiro, bloco=config.BLOCO_TESTE)
        except AssertionError:
            return  # a recusa é o comportamento esperado
        raise AssertionError("a Avaliacao aceitou medir o teste")

    # ----------------------------------------------------------------------------------------------------------------
    # Impressão e gravação
    # ----------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _imprimir_resultados(comparacao: pd.DataFrame, ic: pd.DataFrame, tempos: pd.DataFrame, escolha: dict,
                             dados: DadosModelo) -> None:
        print("\nAs cinco linhas na validação (F1 macro, F1 por classe, recall de FALHA, transições, tamanho):")
        print(f"  {'modelo':<19}{'F1 macro':>9}{'F1 OK':>8}{'F1 RISCO':>10}{'F1 FALHA':>10}{'rec FALHA':>10}"
              f"{'OK→FALHA':>10}{'FALHA→OK':>10}{'árvores':>9}{'folhas':>8}{'nós':>8}")
        for linha in comparacao.itertuples(index=False):
            arvores = "" if pd.isna(linha.arvores) else str(int(linha.arvores))
            folhas = "" if pd.isna(linha.folhas) else str(int(linha.folhas))
            nos = "" if pd.isna(linha.nos) else str(int(linha.nos))
            marca = "  <- escolhida" if linha.escolhido else ""
            print(
                f"  {linha.modelo:<19}{linha.f1_macro:>9.4f}{linha.f1_OK:>8.4f}{linha.f1_RISCO:>10.4f}{linha.f1_FALHA:>10.4f}"
                f"{linha.recall_FALHA:>10.4f}{linha.acerto_OK_para_FALHA:>10.1%}{linha.acerto_FALHA_para_OK:>10.1%}"
                f"{arvores:>9}{folhas:>8}{nos:>8}{marca}"
            )
        print("  (OK→FALHA e FALHA→OK são acertos nas transições agora → futuro; N em comparacao_modelos.csv.)")

        print("\nIC 95 % pareado por fluxo da diferença de F1 macro (não decide):")
        for linha in ic.itertuples(index=False):
            veredito = "exclui o zero" if linha.exclui_zero else "contém o zero"
            print(f"  {linha.modelo} − {linha.referencia}: {linha.diferenca_f1:+.4f}  "
                  f"[{linha.ic_inferior:+.4f}; {linha.ic_superior:+.4f}]  {veredito}")

        print("\nTempos (segundos; a grade inteira, e a mediana de previsão na validação):")
        for modelo in config.ORDEM_FAMILIAS + [config.MODELO_ARVORE]:
            busca = tempos[(tempos["modelo"] == modelo) & (tempos["etapa"] == "busca inteira")]
            previsao = tempos[(tempos["modelo"] == modelo) & tempos["etapa"].str.startswith("previsão")]
            combinacoes = tempos[(tempos["modelo"] == modelo) & (tempos["etapa"] == "treino de uma combinação")]
            texto = f"  {modelo:<19}busca inteira {busca['segundos'].iloc[0]:.1f} s"
            if len(combinacoes):
                texto += (f" | um treino: {combinacoes['segundos'].min():.2f} a {combinacoes['segundos'].max():.2f} s "
                          f"(soma {combinacoes['segundos'].sum():.1f} s)")
            texto += f" | previsão {previsao['segundos'].iloc[0]:.3f} s"
            print(texto)

        print(f"\nEscolha entre as famílias: {escolha['modelo']} (F1 macro {escolha['f1_macro_escolhido']:.4f}).")
        print(f"  {escolha['motivo']}")
        print(f"  Teste fechado: nenhuma linha dele foi lida; só o N ({dados.n_teste}) existe.")

    @staticmethod
    def _gravar(floresta: Floresta, boosting: Boosting, comparacao: pd.DataFrame, matriz: pd.DataFrame,
                ic: pd.DataFrame, importancias: pd.DataFrame, escolha: dict, tempos: pd.DataFrame) -> None:
        """Grava tudo em `data/modelo/comparacao/` (só depois das checagens). `tempos.csv` fica à parte."""
        config.COMPARACAO.mkdir(parents=True, exist_ok=True)
        floresta.quadro_busca().to_csv(config.ARQUIVO_BUSCA_FLORESTA, index=False)
        boosting.quadro_busca().to_csv(config.ARQUIVO_BUSCA_BOOSTING, index=False)
        comparacao.to_csv(config.ARQUIVO_COMPARACAO_MODELOS, index=False)
        matriz.to_csv(config.ARQUIVO_MATRIZ_COMPARACAO, index=False)
        ic.round(config.CASAS_CSV).to_csv(config.ARQUIVO_IC_PAREADO, index=False)
        importancias.to_csv(config.ARQUIVO_IMPORTANCIAS, index=False)
        config.ARQUIVO_ESCOLHA.write_text(json.dumps(escolha, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tempos.to_csv(config.ARQUIVO_TEMPOS, index=False)
        print()
        for arquivo in (
            config.ARQUIVO_BUSCA_FLORESTA, config.ARQUIVO_BUSCA_BOOSTING, config.ARQUIVO_COMPARACAO_MODELOS,
            config.ARQUIVO_MATRIZ_COMPARACAO, config.ARQUIVO_IC_PAREADO, config.ARQUIVO_IMPORTANCIAS,
            config.ARQUIVO_ESCOLHA, config.ARQUIVO_TEMPOS,
        ):
            print(f"Gravado: {arquivo}")

    @staticmethod
    def _verificar_disco(dados: DadosModelo, resultados: dict, floresta: Floresta, boosting: Boosting,
                         escolha: dict, ic: pd.DataFrame) -> None:
        """Relê o que foi gravado: a regra é refeita a partir dos CSVs (busca e comparação) e tudo bate com a memória."""
        casa = 10**-config.CASAS_CSV  # o CSV arredonda: uma unidade da última casa de folga
        n_validacao = dados.resumo[config.BLOCO_VALIDACAO]["n"]

        # Busca de cada família: a escolhida gravada é a que a regra dá a partir do próprio CSV.
        for modelo, arquivo, combinacao, ordem, objeto in (
            (config.MODELO_FLORESTA, config.ARQUIVO_BUSCA_FLORESTA, COMBINACAO_FLORESTA, ORDEM_FLORESTA, floresta),
            (config.MODELO_BOOSTING, config.ARQUIVO_BUSCA_BOOSTING, COMBINACAO_BOOSTING, ORDEM_BOOSTING, boosting),
        ):
            busca = pd.read_csv(arquivo)
            assert set(busca["modelo"]) == {modelo}, f"{arquivo.name}: modelo inesperado"
            assert len(busca) == len(busca[combinacao].drop_duplicates()), f"{arquivo.name}: combinações repetidas"
            assert busca["escolhida"].sum() == 1, f"{arquivo.name}: precisa ter exatamente uma escolhida"
            gravada = busca[busca["escolhida"]].iloc[0]
            refeita = busca.loc[escolher_por_regra(busca, ordem)]
            assert refeita[combinacao].equals(gravada[combinacao]), f"{modelo}: a regra refeita do CSV não dá a escolhida gravada"
            assert abs(gravada["f1_macro_validacao"] - resultados[modelo].f1_macro) <= casa, f"{modelo}: F1 da busca ≠ F1 medido"
            # A escolhida gravada é a árvore treinada (mesmos hiperparâmetros do modelo guardado).
            assert int(gravada["n_estimators"]) == int(objeto.modelo.n_estimators), f"{modelo}: escolhida gravada ≠ modelo"

        # Comparação: as cinco linhas, a escolhida marcada, o F1 de cada uma igual ao medido.
        comparacao = pd.read_csv(config.ARQUIVO_COMPARACAO_MODELOS).set_index("modelo")
        assert list(comparacao.index) == list(resultados), "comparacao_modelos.csv com outras linhas"
        for modelo, r in resultados.items():
            assert abs(comparacao.loc[modelo, "f1_macro"] - r.f1_macro) <= casa, f"{modelo}: F1 em comparacao_modelos.csv"
        assert comparacao["escolhido"].sum() == 1 and comparacao.loc[escolha["modelo"], "escolhido"], "escolhido não bate"

        # A escolha entre famílias, refeita a partir do CSV de comparação (com a mesma ordem de simplicidade).
        candidatas = comparacao.loc[list(config.ORDEM_FAMILIAS), ["f1_macro"]].rename(columns={"f1_macro": "f1_macro_validacao"})
        candidatas = candidatas.reset_index()
        candidatas["posicao"] = range(1, len(candidatas) + 1)
        refeita = str(candidatas.loc[escolher_por_regra(candidatas, [("posicao", True)]), "modelo"])
        assert refeita == escolha["modelo"], f"a regra refeita do CSV escolhe {refeita}, e o arquivo diz {escolha['modelo']}"

        # escolha.json: o que está no disco é o que foi gerado.
        gravado = json.loads(config.ARQUIVO_ESCOLHA.read_text(encoding="utf-8"))
        assert gravado == json.loads(json.dumps(escolha, ensure_ascii=False)), "escolha.json diferente do gerado"

        # Matriz: as cinco linhas, cada uma somando o N da validação.
        matriz_gravada = pd.read_csv(config.ARQUIVO_MATRIZ_COMPARACAO)
        colunas = [f"previsto_{classe}" for classe in config.CLASSES]
        somas = matriz_gravada.groupby("modelo")[colunas].sum().sum(axis=1)
        assert (somas == n_validacao).all(), f"matriz_comparacao.csv não soma o N da validação: {dict(somas)}"

        # IC gravado: uma linha por par, com os mesmos limites que a memória, e o veredito consistente.
        ic_gravado = pd.read_csv(config.ARQUIVO_IC_PAREADO)
        assert len(ic_gravado) == len(PARES_IC), "ic_pareado.csv com outro número de pares"
        for antes, depois in zip(ic.round(config.CASAS_CSV).itertuples(index=False), ic_gravado.itertuples(index=False)):
            assert abs(antes.ic_inferior - depois.ic_inferior) <= casa and abs(antes.ic_superior - depois.ic_superior) <= casa, (
                "limites do IC gravados diferentes dos calculados"
            )
            assert bool(depois.exclui_zero) == (depois.ic_inferior > 0 or depois.ic_superior < 0), "exclui_zero gravado errado"

        # Importâncias: cada modelo soma 1 (arredondado a 6 casas, com folga de dez unidades).
        importancias = pd.read_csv(config.ARQUIVO_IMPORTANCIAS)
        soma = importancias.groupby("modelo")["importancia"].sum()
        assert (np.abs(soma - 1) <= 10 * casa).all(), f"importâncias não somam 1: {dict(soma)}"

        # Tempos: existem e só os modelos da comparação aparecem (fora da checagem de arquivos iguais).
        tempos = pd.read_csv(config.ARQUIVO_TEMPOS)
        # A persistência não tem treino nem árvore: não tem tempo. Os outros quatro modelos têm.
        assert set(tempos["modelo"]) == set(resultados) - {config.MODELO_PERSISTENCIA}, "tempos.csv com outros modelos"

        # Só os arquivos previstos estão em data/modelo/comparacao/ (o `comparar` não deixa lixo).
        esperados = {
            config.ARQUIVO_BUSCA_FLORESTA.name, config.ARQUIVO_BUSCA_BOOSTING.name, config.ARQUIVO_COMPARACAO_MODELOS.name,
            config.ARQUIVO_MATRIZ_COMPARACAO.name, config.ARQUIVO_IC_PAREADO.name, config.ARQUIVO_IMPORTANCIAS.name,
            config.ARQUIVO_ESCOLHA.name, config.ARQUIVO_TEMPOS.name,
        }
        no_disco = {arquivo.name for arquivo in config.COMPARACAO.iterdir()}
        assert no_disco == esperados, f"arquivos inesperados em data/modelo/comparacao/: {sorted(no_disco ^ esperados)}"
