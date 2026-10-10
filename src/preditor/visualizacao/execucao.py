"""Orquestra o replay: prevê a validação com a Random Forest exportada, grava o JSON e verifica (SPEC-replay-floresta.md).

Roda sem Spark e sem Java: só pandas, scikit-learn e o `.joblib` exportado sobre o Parquet do Gold. Não refaz árvore
nenhuma: a previsão vem do arquivo, conferido contra o LEIA-ME, e o placar é conferido contra a comparação.
"""

import hashlib
import json

import pandas as pd

from preditor import config
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.dados import DadosModelo
from preditor.visualizacao.exportacao import EPOCA, NOME_DA_FLORESTA, ExportadorReplay
from preditor.visualizacao.modelo_exportado import ModeloExportado
from preditor.visualizacao.rotas import Geografia, Sondas

# Os campos de cada medição no JSON (SPEC-visualizacao.md, "Formato do `replay.json`"). `t_futuro` (V5) = instante,
# em segundos UTC, da medição de onde vem o `futuro`. Não há `x`, `folha` nem árvore: a página só mostra a previsão e o
# modelo que a fez (SPEC-replay-floresta.md). As rotas (`trechos`) ficam em `fluxos`, não nas medições.
CAMPOS_MEDICAO = {"f", "t", "rtt", "timeout", "atual", "previsto", "futuro", "conferivel", "t_futuro"}


class ExecucaoReplay:
    def executar(self) -> None:
        # O bloco do teste fica fechado até a Tarefa 5 (AGENTS.md): o replay recusa o bloco antes de ler qualquer coisa.
        assert config.BLOCO_REPLAY != config.BLOCO_TESTE, (
            f"BLOCO_REPLAY = {config.BLOCO_REPLAY!r}: o teste só pode ser exibido depois da Tarefa 5"
        )
        # Sem o Gold no disco, `DadosModelo` termina com a mensagem de qual comando rodar antes.
        dados = DadosModelo().carregar()
        # Falha cedo: sem a comparação, não há o que conferir o placar (pede `comparar` logo de início).
        self._exigir_arquivos_da_comparacao()
        # Também falha cedo sem `sondas.csv` (pede o script que o gera); o replay só lê o CSV, nunca a API.
        Sondas.ler()
        bloco = ExportadorReplay.ler_validacao()

        # A previsão vem do `.joblib` exportado, depois de conferido contra o LEIA-ME. Nada é treinado aqui.
        exportado = ModeloExportado.ler()
        previsto = ExportadorReplay.prever(bloco, exportado.modelo)
        texto = self._exportar(bloco, previsto, exportado)

        # Verifica ANTES de gravar, sobre o JSON em memória: um arquivo reprovado nunca chega a `web/dados/`.
        documento = json.loads(texto)
        self._verificar_antes_de_gravar(dados, bloco, previsto, exportado)
        self._verificar_documento(documento, dados)
        self._verificar_modelo(documento, exportado)
        self._verificar_previsoes(documento, bloco)
        self._verificar_rotas(documento)
        self._verificar_sem_teste(documento)
        self._verificar_metricas(documento)
        self._verificar_determinismo(bloco, exportado, texto)

        config.ARQUIVO_REPLAY.parent.mkdir(parents=True, exist_ok=True)
        config.ARQUIVO_REPLAY.write_text(texto, encoding="utf-8", newline="\n")
        # Só conferência: o que a página vai ler é igual ao texto que passou nas checagens.
        assert config.ARQUIVO_REPLAY.read_text(encoding="utf-8") == texto, "o arquivo gravado difere do texto verificado"
        print(f"Gravado: {config.ARQUIVO_REPLAY} ({len(texto.encode('utf-8')) / 1e6:.2f} MB)")
        self._imprimir_rotas(documento)

    @staticmethod
    def _exigir_arquivos_da_comparacao() -> None:
        """A matriz e as métricas da comparação são a referência das checagens: sem elas, pede `comparar` logo de início."""
        for arquivo in (config.ARQUIVO_COMPARACAO_MODELOS, config.ARQUIVO_MATRIZ_COMPARACAO):
            if not arquivo.exists():
                raise SystemExit(f"Não encontrei {arquivo}.\nRode antes: uv run python -m preditor comparar")

    @staticmethod
    def _exportar(bloco: pd.DataFrame, previsto: pd.Series, exportado: ModeloExportado) -> str:
        """Monta o documento com a previsão da floresta e devolve o texto do JSON (a exportação, sem treinar nada)."""
        return ExportadorReplay.texto(ExportadorReplay.montar(bloco, previsto, ExportadorReplay.bloco_modelo(exportado)))

    @staticmethod
    def _verificar_antes_de_gravar(
        dados: DadosModelo, bloco: pd.DataFrame, previsto: pd.Series, exportado: ModeloExportado
    ) -> None:
        """Confere, ainda em memória, que as linhas conferíveis são exatamente as da validação medida, e a previsão delas."""
        validacao = config.BLOCO_VALIDACAO
        conferiveis = bloco.index[bloco["conferivel"]]
        # O índice de cada linha é o do Parquet: o mesmo conjunto de linhas, não só o mesmo número delas.
        assert conferiveis.sort_values().equals(dados.y[validacao].index.sort_values()), (
            "as medições conferíveis não são as linhas da validação do DadosModelo"
        )
        assert len(conferiveis) == dados.resumo[validacao]["n"], (
            f"{len(conferiveis)} conferíveis, mas o N da validação é {dados.resumo[validacao]['n']}"
        )
        # A previsão exportada, nas linhas que o DadosModelo mediu, é a que a floresta dá a esses mesmos X.
        X_validacao = dados.x_ajustado(validacao)
        esperada = pd.Series(exportado.modelo.predict(X_validacao), index=X_validacao.index)
        assert previsto.loc[X_validacao.index].equals(esperada), "a previsão exportada difere da floresta nas linhas medidas"
        # O futuro exportado das conferíveis é o alvo que a floresta usou na comparação.
        assert bloco.loc[conferiveis, config.ALVO].equals(dados.y[validacao].loc[conferiveis]), (
            "o futuro das conferíveis difere do alvo do DadosModelo"
        )

    @staticmethod
    def _verificar_documento(documento: dict, dados: DadosModelo) -> None:
        """Checagens do que está no arquivo: estrutura, ordem de tempo, fluxos e campos."""
        meta, fluxos, medicoes = documento["meta"], documento["fluxos"], documento["medicoes"]
        assert meta["bloco"] == config.BLOCO_REPLAY and meta["classes"] == list(config.CLASSES), "meta inesperada"
        assert meta["aviso"] == config.AVISO_ROTA, "o aviso de rota ilustrativa não está no JSON"

        ids = [fluxo["id"] for fluxo in fluxos]
        assert len(ids) == len(set(ids)), "fluxo repetido no JSON"

        tempos = [m["t"] for m in medicoes]
        assert tempos == sorted(tempos), "medições fora de ordem de `t`"
        assert meta["inicio"] == ExportadorReplay.formatar_instante(tempos[0]), "meta.inicio não bate com a 1ª medição"
        assert meta["fim"] == ExportadorReplay.formatar_instante(tempos[-1]), "meta.fim não bate com a última medição"

        classes = set(config.CLASSES)
        for medicao in medicoes:
            assert set(medicao) == CAMPOS_MEDICAO, f"campos inesperados: {sorted(medicao)}"
            assert 0 <= medicao["f"] < len(fluxos), f"`f` aponta para um fluxo que não existe: {medicao['f']}"
            assert medicao["atual"] in classes and medicao["previsto"] in classes, f"classe fora de {config.CLASSES}"
            assert medicao["timeout"] in (0, 1), f"timeout fora de 0 ou 1: {medicao['timeout']}"
            # Sem resposta nenhuma (timeout) o RTT é nulo; com resposta, é positivo (RTT válido = rtt > 0).
            assert (medicao["rtt"] is None) == (medicao["timeout"] == 1), "rtt nulo e timeout não coincidem"
            assert medicao["rtt"] is None or medicao["rtt"] > 0, "rtt <= 0 no JSON"
            # `futuro` só existe nas conferíveis (as do placar); nas demais é nulo.
            assert (medicao["futuro"] in classes) == medicao["conferivel"], "futuro e conferivel não coincidem"
        assert {medicao["f"] for medicao in medicoes} == set(range(len(fluxos))), "fluxo sem nenhuma medição"
        ExecucaoReplay._verificar_t_futuro(medicoes, tempos[-1])

        n_conferiveis = sum(medicao["conferivel"] for medicao in medicoes)
        n_validacao = dados.resumo[config.BLOCO_VALIDACAO]["n"]
        assert n_conferiveis == n_validacao, f"{n_conferiveis} conferíveis no JSON, N da validação = {n_validacao}"
        print(
            f"JSON: {len(medicoes)} medições | {len(fluxos)} fluxos | {n_conferiveis} conferíveis (= N da validação) | "
            f"{meta['inicio']} a {meta['fim']}"
        )

    @staticmethod
    def _verificar_t_futuro(medicoes: list[dict], fim: int) -> None:
        """`t_futuro` (V5): preenchido só nas conferíveis, de 10 a 14 min depois, dentro do bloco, e conferido por outro caminho."""
        # Caminho independente do Gold: usa só o que está no JSON. (fluxo, instante) → `atual` daquela medição, e os
        # instantes de cada fluxo em ordem (as medições já estão em ordem de `t`).
        atual_em = {(m["f"], m["t"]): m["atual"] for m in medicoes}
        instantes_do_fluxo: dict[int, list[int]] = {}
        for medicao in medicoes:
            instantes_do_fluxo.setdefault(medicao["f"], []).append(medicao["t"])

        for medicao in medicoes:
            t_futuro = medicao["t_futuro"]
            # Preenchido se e somente se a medição é conferível.
            assert (t_futuro is not None) == medicao["conferivel"], "t_futuro e conferivel não coincidem"
            if t_futuro is None:
                continue
            # A 3ª medição seguinte está de 600 a 840 s depois (RFC §3) e dentro do bloco exibido (nunca no teste).
            assert config.FUTURO_MIN_S <= t_futuro - medicao["t"] <= config.FUTURO_MAX_S, (
                f"t_futuro - t fora de {config.FUTURO_MIN_S} a {config.FUTURO_MAX_S} s: {t_futuro - medicao['t']}"
            )
            assert t_futuro <= fim, "t_futuro depois do fim do bloco exibido"
            # Existe uma medição do mesmo fluxo nesse instante, e o `atual` dela é o `futuro` gravado.
            assert (medicao["f"], t_futuro) in atual_em, "não há medição do mesmo fluxo em t_futuro"
            assert atual_em[(medicao["f"], t_futuro)] == medicao["futuro"], "o atual em t_futuro difere do futuro gravado"
            # É a PASSOS_FUTURO-ésima seguinte: contando as medições do fluxo em (t, t_futuro], são exatamente 3.
            entre = sum(medicao["t"] < instante <= t_futuro for instante in instantes_do_fluxo[medicao["f"]])
            assert entre == config.PASSOS_FUTURO, f"t_futuro é a {entre}ª medição seguinte, não a {config.PASSOS_FUTURO}ª"
        n = sum(medicao["conferivel"] for medicao in medicoes)
        print(f"t_futuro: {n} preenchidos (= conferíveis) | 600 a 840 s depois | até o fim do bloco | atual em t_futuro = futuro | 3ª seguinte")

    @staticmethod
    def _verificar_modelo(documento: dict, exportado: ModeloExportado) -> None:
        """O bloco `modelo` é o que o arquivo exportado diz: SHA-256 (o do LEIA-ME), família, árvores, parâmetros e colunas."""
        bloco, floresta = documento["modelo"], exportado.modelo
        # O SHA-256 gravado é o do arquivo que foi aberto, e este já bateu com o LEIA-ME na leitura.
        sha_do_arquivo = hashlib.sha256(config.ARQUIVO_MODELO_FINAL.read_bytes()).hexdigest()
        assert bloco["sha256"] == exportado.sha256 == sha_do_arquivo, "SHA-256 do modelo no JSON difere do arquivo"
        assert bloco["nome"] == NOME_DA_FLORESTA and bloco["familia"] == config.MODELO_FLORESTA, "nome ou família do modelo"
        # A floresta tem o número de árvores gravado, e a conta das árvores é a da própria floresta.
        assert bloco["arvores"] == len(floresta.estimators_) == floresta.n_estimators == exportado.parametros["n_estimators"], (
            f"árvores: JSON {bloco['arvores']}, arquivo {len(floresta.estimators_)}"
        )
        assert bloco["parametros"] == exportado.parametros, "parâmetros do JSON diferentes do escolha.json"
        # As 10 colunas da floresta, na ordem, e só elas: nenhuma coluna proibida entrou no modelo.
        assert bloco["colunas"] == list(floresta.feature_names_in_) == DadosModelo.colunas_ajustadas(), "colunas do modelo"
        assert not set(bloco["colunas"]) & set(config.COLUNAS_PROIBIDAS), "coluna proibida no modelo"
        assert set(floresta.classes_) == set(config.CLASSES), "classes do modelo diferentes de OK, RISCO e FALHA"
        print(
            f"Modelo: {bloco['nome']}, {bloco['arvores']} árvores | SHA-256 {bloco['sha256'][:12]}… = LEIA-ME | "
            f"{len(bloco['colunas'])} colunas (= as do .joblib, sem proibida)"
        )

    @staticmethod
    def _verificar_previsoes(documento: dict, bloco: pd.DataFrame) -> None:
        """Cada previsão do JSON é a que o modelo RECARREGADO dá à mesma linha do Gold, medição por medição."""
        # Segunda carga do arquivo (com a conferência de novo): o que o JSON mostra não depende do objeto da execução.
        recarregado = ModeloExportado.ler().modelo
        ordenado = bloco.sort_values(["t", "fluxo_id"], kind="stable")
        X = ExportadorReplay.x(ordenado)  # o X exato do Gold, sem nada preenchido
        previsto_json = [medicao["previsto"] for medicao in documento["medicoes"]]
        assert list(recarregado.predict(X)) == previsto_json, "uma previsão do JSON difere da do modelo recarregado"
        # Ausente continua ausente: a floresta viu os mesmos nulos do Gold, coluna a coluna (RFC §8.3).
        assert (X.isna().sum() == ordenado[DadosModelo.colunas_ajustadas()].isna().sum()).all(), "nulos do X ≠ nulos do Gold"
        com_ausente = int(X.isna().any(axis=1).sum())
        print(
            f"Previsões: {len(previsto_json)} do JSON = modelo recarregado, linha a linha | {com_ausente} medições com "
            "algum valor ausente, previstas sem preencher"
        )

    @staticmethod
    def _verificar_rotas(documento: dict) -> None:
        """Checagens das rotas simuladas: início e fim, encadeamento, coordenadas, cabos, km e RTT mínimo."""
        sondas = Sondas.ler()
        # As sondas do Gold (as 13 do dataset) e as do CSV são as mesmas: faltar sonda no CSV impediria montar a rota,
        # e sobrar sonda no CSV seria um arquivo desatualizado em relação ao Gold.
        sondas_do_gold = set(Sondas.do_gold())
        assert sondas_do_gold == set(sondas), (
            f"sondas do Gold != sondas de {config.ARQUIVO_SONDAS.name}: "
            f"só no Gold {sorted(sondas_do_gold - set(sondas))}, só no CSV {sorted(set(sondas) - sondas_do_gold)}"
        )

        # Sanidade do haversine, incluindo o meridiano 180 (as rotas do Pacífico o cruzam): 1° de longitude no
        # equador = 111,19 km, e 179° → -179° é 2° de arco, não 358°.
        assert abs(Geografia.distancia_km([0, 0], [0, 90]) - 10007.54) < 0.1, "haversine: quarto de meridiano errado"
        assert abs(Geografia.distancia_km([179, 0], [-179, 0]) - 222.39) < 0.1, "haversine: erra ao cruzar o meridiano 180"

        tipos_de_no = {"sonda", "pop", "aterragem", "destino"}
        medianas = ExportadorReplay.ler_medianas()  # a que o cartão mostra ao lado do RTT mínimo
        for fluxo in documento["fluxos"]:
            rotulo = fluxo["id"]
            mediana = medianas.loc[rotulo]
            assert (fluxo["mediana_ms"] is None) == pd.isna(mediana), f"{rotulo}: mediana_ms nula e baseline insuficiente não coincidem"
            assert pd.isna(mediana) or fluxo["mediana_ms"] == round(float(mediana), config.CASAS_RTT_REPLAY), f"{rotulo}: mediana_ms"
            trechos = fluxo["trechos"]
            assert trechos, f"{rotulo}: rota sem trechos"
            assert fluxo["opcao"] in [opcao["nome"] for opcao in config.ROTAS_POR_PAIS[fluxo["pais"]]], f"{rotulo}: opção desconhecida"

            # Começa na sonda (a do CSV) e termina no destino.
            prb_id = int(rotulo.split("|")[0])
            primeiro, ultimo = trechos[0]["nos"][0], trechos[-1]["nos"][-1]
            assert primeiro["tipo"] == "sonda" and primeiro["nome"] == f"sonda {prb_id}", f"{rotulo}: a rota não começa na sonda"
            esperado = [round(coordenada, config.CASAS_COORDENADA) for coordenada in sondas[prb_id]]
            assert primeiro["ponto"] == esperado, f"{rotulo}: a sonda não está onde o CSV diz"
            assert ultimo["tipo"] == "destino", f"{rotulo}: a rota não termina no destino"
            # O nome do destino é "Cidade (dst_addr)": a cidade é um dos pontos candidatos do país, e o nó está a
            # no máximo `DESLOCAMENTO_DESTINO_GRAUS` dele.
            cidade = ultimo["nome"].split(" (")[0]
            pontos_do_pais = dict(config.PONTOS_DESTINO[fluxo["pais"]])
            assert cidade in pontos_do_pais, f"{rotulo}: destino em {cidade!r}, fora de {list(pontos_do_pais)}"
            longitude, latitude = pontos_do_pais[cidade]
            assert abs(ultimo["ponto"][0] - longitude) <= config.DESLOCAMENTO_DESTINO_GRAUS + 1e-9
            assert abs(ultimo["ponto"][1] - latitude) <= config.DESLOCAMENTO_DESTINO_GRAUS + 1e-9

            for anterior, seguinte in zip(trechos, trechos[1:]):
                # Trechos encadeados: o último nó de um é o primeiro do seguinte (mesmo tipo, nome e ponto).
                assert anterior["nos"][-1] == seguinte["nos"][0], f"{rotulo}: trechos não encadeados em {anterior['nos'][-1]['nome']}"

            for trecho in trechos:
                assert trecho["tipo"] in ("terrestre", "submarino"), f"{rotulo}: tipo de trecho {trecho['tipo']!r}"
                for no in trecho["nos"]:
                    assert no["tipo"] in tipos_de_no, f"{rotulo}: tipo de nó {no['tipo']!r}"
                    # Coordenadas válidas ([longitude, latitude]): lon de -180 a 180, lat de -90 a 90.
                    assert -180 <= no["ponto"][0] <= 180 and -90 <= no["ponto"][1] <= 90, f"{rotulo}: coordenada inválida {no}"
                for ponto in trecho["caminho"]:
                    assert -180 <= ponto[0] <= 180 and -90 <= ponto[1] <= 90, f"{rotulo}: coordenada inválida {ponto}"
                # O caminho (a linha desenhada) começa e termina nos nós do trecho.
                assert trecho["caminho"][0] == trecho["nos"][0]["ponto"] and trecho["caminho"][-1] == trecho["nos"][-1]["ponto"]
                if trecho["tipo"] == "submarino":
                    # Cabo do catálogo, ligando estações de aterragem (todos os nós de um trecho submarino são estações).
                    assert trecho["nome"] in config.CABOS, f"{rotulo}: cabo {trecho['nome']!r} fora do catálogo"
                    estacoes_do_cabo = [ponto for ponto in config.CABOS[trecho["nome"]]["pontos"] if isinstance(ponto, str)]
                    for no in trecho["nos"]:
                        assert no["tipo"] == "aterragem" and no["nome"] in estacoes_do_cabo, f"{rotulo}: {no['nome']} não é estação do {trecho['nome']}"
                    assert len(trecho["nos"]) >= 2, f"{rotulo}: trecho submarino com menos de 2 estações"
                else:
                    assert [no["ponto"] for no in trecho["nos"]] == trecho["caminho"], f"{rotulo}: o trecho terrestre não segue os nós"
                # km do trecho = soma das distâncias entre pontos consecutivos do caminho que está no arquivo.
                assert trecho["km"] == round(Geografia.comprimento_km(trecho["caminho"]), config.CASAS_KM), f"{rotulo}: km do trecho"

            # Fora do Brasil, ao menos um cabo submarino; no Brasil, nenhum (só backbone por terra).
            n_submarinos = sum(trecho["tipo"] == "submarino" for trecho in trechos)
            assert (n_submarinos > 0) == (fluxo["pais"] != "BR"), f"{rotulo}: {n_submarinos} trechos submarinos para {fluxo['pais']}"

            # km da rota = soma dos trechos; RTT mínimo = 2 × km / 200.
            assert fluxo["km"] == round(sum(trecho["km"] for trecho in trechos), config.CASAS_KM), f"{rotulo}: km da rota"
            assert fluxo["rtt_minimo_ms"] == round(2 * fluxo["km"] / config.VELOCIDADE_FIBRA_KM_POR_MS, config.CASAS_RTT_REPLAY), (
                f"{rotulo}: rtt_minimo_ms"
            )
        print(
            f"Rotas: {len(documento['fluxos'])} fluxos, {len(sondas)} sondas no CSV | começam na sonda e terminam no destino | "
            "trechos encadeados | cabos do catálogo | km e RTT mínimo recalculados"
        )

    @staticmethod
    def _imprimir_rotas(documento: dict) -> None:
        """Por região: as rotas usadas, quantos fluxos em cada, km e RTT mínimo teórico ao lado da mediana real do baseline."""
        baseline = ExportadorReplay.ler_medianas()
        linhas = pd.DataFrame(
            [
                {
                    "regiao": fluxo["regiao"],
                    "pais": fluxo["pais"],
                    "opcao": fluxo["opcao"],
                    # O nó final se chama "Cidade (dst_addr)": só a cidade interessa (um país pode ter mais de uma).
                    "destino": fluxo["trechos"][-1]["nos"][-1]["nome"].split(" (")[0],
                    "id": fluxo["id"],
                    "km": fluxo["km"],
                    "rtt_minimo_ms": fluxo["rtt_minimo_ms"],
                    "mediana_ms": baseline.get(fluxo["id"], float("nan")),
                }
                for fluxo in documento["fluxos"]
            ]
        )
        # RTT mínimo acima da mediana real = impossível para aquele caminho (a luz na fibra não chega a tempo).
        # A rota é simulada, então não é erro do comando: é só uma contagem para quem confere as rotas.
        linhas["impossivel"] = linhas["rtt_minimo_ms"] > linhas["mediana_ms"]

        def faixa(serie: pd.Series, casas: int) -> str:
            return f"{serie.min():.{casas}f} a {serie.max():.{casas}f}"

        print("\nRotas por região (rota simulada; RTT mínimo teórico = 2 × km / 200, ao lado da mediana real do baseline)")
        print(
            f"{'região / país':<22}{'rota':<26}{'destino':<16}{'fluxos':>7}  {'km':<14}{'RTT mín (ms)':<16}"
            f"{'mediana real (ms)':<19}{'acima da mediana':>17}"
        )
        for (regiao, pais, opcao, destino), grupo in linhas.groupby(["regiao", "pais", "opcao", "destino"], sort=True):
            print(
                f"{regiao + ' (' + pais + ')':<22}{opcao:<26}{destino:<16}{len(grupo):>7}  {faixa(grupo['km'], 0):<14}"
                f"{faixa(grupo['rtt_minimo_ms'], 1):<16}{faixa(grupo['mediana_ms'], 1):<19}{int(grupo['impossivel'].sum()):>17}"
            )

        impossiveis = linhas[linhas["impossivel"]].sort_values(["regiao", "pais", "id"])
        # Só uma contagem: a rota é ilustrativa, então nenhum valor aqui reprova o comando.
        print(f"\n{len(impossiveis)} fluxos com RTT mínimo acima da mediana real")
        # Se sobrar algum, a lista fica à vista (não se esconde): mostra onde a rota simulada não cabe na medição.
        for linha in impossiveis.itertuples():
            print(
                f"  {linha.id:<34} {linha.regiao} ({linha.pais}) | {linha.opcao} → {linha.destino} | {linha.km:.0f} km | "
                f"mínimo {linha.rtt_minimo_ms:.1f} ms > mediana {linha.mediana_ms:.1f} ms"
            )

    @staticmethod
    def _verificar_sem_teste(documento: dict) -> None:
        """Nenhuma medição do bloco teste no JSON, conferido contra uma leitura nova do Gold."""
        completo = DadosModelo._ler()
        teste = completo[completo["bloco"] == config.BLOCO_TESTE]
        exibido = completo[completo["bloco"] == config.BLOCO_REPLAY]
        fluxos, medicoes = documento["fluxos"], documento["medicoes"]

        # Mesmo número de medições que o bloco exibido tem no Gold, todas dentro do tempo dele (o teste vem depois).
        assert len(medicoes) == len(exibido), f"{len(medicoes)} medições no JSON, o bloco tem {len(exibido)}"
        ultimo = pd.Timestamp(medicoes[-1]["t"], unit="s")
        assert ultimo < teste["t"].min(), "o JSON tem medição no tempo do teste"
        # Nem o instante do futuro (V5) cai no tempo do teste: o placar só enxerga a validação.
        ultimo_futuro = max(m["t_futuro"] for m in medicoes if m["t_futuro"] is not None)
        assert pd.Timestamp(ultimo_futuro, unit="s") < teste["t"].min(), "um t_futuro cai no tempo do teste"
        # Nenhum par (fluxo_id, t) do JSON é de uma linha do teste.
        segundos_do_teste = (teste["t"] - EPOCA) // pd.Timedelta(seconds=1)
        chaves_do_teste = set(zip(teste["fluxo_id"], segundos_do_teste))
        chaves_do_json = {(fluxos[m["f"]]["id"], m["t"]) for m in medicoes}
        assert len(chaves_do_json) == len(medicoes), "par (fluxo, t) repetido no JSON"
        assert not chaves_do_json & chaves_do_teste, "o JSON tem medição do bloco teste"

        # Cada fluxo tem um só país e uma só região no Gold, e são os que o JSON mostra.
        por_fluxo = completo.groupby("fluxo_id")[["destination_region", "destination_country"]]
        assert (por_fluxo.nunique() == 1).all().all(), "fluxo com mais de um país ou região"
        regiao_e_pais = por_fluxo.first()
        for fluxo in fluxos:
            esperado = regiao_e_pais.loc[fluxo["id"]]
            assert (fluxo["regiao"], fluxo["pais"]) == (esperado["destination_region"], esperado["destination_country"])
        print(f"Teste fora do JSON: {len(teste)} linhas do teste no Gold, nenhuma no replay")

    @staticmethod
    def _verificar_metricas(documento: dict) -> None:
        """Recalcula matriz e F1 macro só com o JSON (conferíveis) e compara com a comparação: a floresta e a persistência."""
        matriz_csv = pd.read_csv(config.ARQUIVO_MATRIZ_COMPARACAO)
        metricas_csv = pd.read_csv(config.ARQUIVO_COMPARACAO_MODELOS)

        conferiveis = pd.DataFrame([m for m in documento["medicoes"] if m["conferivel"]])
        colunas = [f"previsto_{classe}" for classe in config.CLASSES]
        # A floresta é lida de `previsto` (o que a página mostra); a persistência, de `atual` (o "palpite simples").
        for modelo, coluna in ((config.MODELO_FLORESTA, "previsto"), (config.MODELO_PERSISTENCIA, "atual")):
            resultado = Avaliacao.medir(conferiveis["futuro"], conferiveis[coluna], bloco=config.BLOCO_REPLAY)

            esperada = matriz_csv[matriz_csv["modelo"] == modelo].set_index("verdadeiro").loc[list(config.CLASSES), colunas]
            assert (resultado.matriz.to_numpy() == esperada.to_numpy()).all(), (
                f"{modelo}: a matriz recalculada do JSON difere de {config.ARQUIVO_MATRIZ_COMPARACAO.name}"
            )
            f1_csv = metricas_csv[metricas_csv["modelo"] == modelo]["f1_macro"].item()
            # O CSV tem o F1 arredondado a `CASAS_CSV` casas: aceita até meia unidade da última casa.
            assert abs(resultado.f1_macro - f1_csv) <= 0.5 * 10**-config.CASAS_CSV, (
                f"{modelo}: F1 macro do JSON {resultado.f1_macro:.6f} difere do CSV {f1_csv:.6f}"
            )
            acertos = int(resultado.matriz.to_numpy().diagonal().sum())
            print(f"  {modelo:<14} F1 macro {resultado.f1_macro:.4f} = CSV | acertos {acertos} de {resultado.n}")
        print(f"Matriz e F1 macro recalculados do JSON = {config.ARQUIVO_MATRIZ_COMPARACAO.name} e {config.ARQUIVO_COMPARACAO_MODELOS.name}")

    @staticmethod
    def _verificar_determinismo(bloco: pd.DataFrame, exportado: ModeloExportado, texto: str) -> None:
        """Mesmo arquivo e mesma entrada = mesmo JSON: refaz a previsão e a exportação e compara byte a byte."""
        refeito = ExportadorReplay.prever(bloco, exportado.modelo)
        assert ExecucaoReplay._exportar(bloco, refeito, exportado) == texto, "exportar duas vezes deu um arquivo diferente"
        print(f"Mesma entrada = mesmo JSON (sha256 {hashlib.sha256(texto.encode('utf-8')).hexdigest()[:16]})")
