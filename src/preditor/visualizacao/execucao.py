"""Orquestra o replay: refaz a árvore oficial, exporta a validação, grava o JSON e verifica (SPEC-visualizacao.md).

Roda sem Spark e sem Java: só pandas + scikit-learn sobre o Parquet do Gold.
"""

import hashlib
import json

import numpy as np
import pandas as pd

from preditor import config
from preditor.modelo.arvore import Arvore
from preditor.modelo.avaliacao import Avaliacao
from preditor.modelo.dados import BLOCOS_USADOS, DadosModelo
from preditor.modelo.regras import Regra, Regras
from preditor.visualizacao.exportacao import EPOCA, ExportadorReplay
from preditor.visualizacao.rotas import Geografia, Sondas

# Os campos de cada medição no JSON (SPEC-visualizacao.md, "Formato do `replay.json`"). `t_futuro` (V5) = instante,
# em segundos UTC, da medição de onde vem o `futuro`; `x` e `folha` (V6) = as 8 colunas que a árvore viu e a folha
# que decidiu a previsão. As rotas (`trechos`) ficam em `fluxos`, não nas medições.
CAMPOS_MEDICAO = {"f", "t", "rtt", "timeout", "atual", "previsto", "futuro", "conferivel", "t_futuro", "x", "folha"}


class ExecucaoReplay:
    def executar(self) -> None:
        # O bloco do teste fica fechado até a Tarefa 5 (AGENTS.md): o replay recusa o bloco antes de ler qualquer coisa.
        assert config.BLOCO_REPLAY != config.BLOCO_TESTE, (
            f"BLOCO_REPLAY = {config.BLOCO_REPLAY!r}: o teste só pode ser exibido depois da Tarefa 5"
        )
        # Sem o Gold no disco, `DadosModelo` termina com a mensagem de qual comando rodar antes.
        dados = DadosModelo().carregar()
        # Falha cedo: sem os arquivos da árvore, não vale gastar a busca (~20 s) para descobrir isso no fim.
        self._exigir_arquivos_da_arvore()
        # Também falha cedo sem `sondas.csv` (pede o script que o gera); o replay só lê o CSV, nunca a API.
        Sondas.ler()
        bloco = ExportadorReplay.ler_validacao()

        # `arvore` não grava o modelo treinado, só a descrição dele: com a mesma semente, a busca refaz a mesma árvore.
        arvore = Arvore().buscar(dados)
        self._conferir_com_arvore_oficial(arvore)
        # Uma regra em português para CADA folha (a página mostra a da folha que decidiu cada previsão).
        regras = ExportadorReplay.regras_das_folhas(arvore, dados)
        texto = self._exportar(bloco, arvore, regras)

        # Verifica ANTES de gravar, sobre o JSON em memória: um arquivo reprovado nunca chega a `web/dados/`.
        documento = json.loads(texto)
        self._verificar_antes_de_gravar(dados, bloco, arvore)
        self._verificar_documento(documento, dados)
        self._verificar_x_e_folhas(documento, bloco, arvore, dados, regras)
        self._verificar_rotas(documento)
        self._verificar_sem_teste(documento)
        self._verificar_metricas(documento)
        self._verificar_determinismo(bloco, arvore, regras, texto)

        config.ARQUIVO_REPLAY.parent.mkdir(parents=True, exist_ok=True)
        config.ARQUIVO_REPLAY.write_text(texto, encoding="utf-8", newline="\n")
        # Só conferência: o que a página vai ler é igual ao texto que passou nas checagens.
        assert config.ARQUIVO_REPLAY.read_text(encoding="utf-8") == texto, "o arquivo gravado difere do texto verificado"
        print(f"Gravado: {config.ARQUIVO_REPLAY} ({len(texto.encode('utf-8')) / 1e6:.2f} MB)")
        self._imprimir_rotas(documento)

    @staticmethod
    def _exigir_arquivos_da_arvore() -> None:
        """A árvore oficial e as métricas dela são a referência das checagens: sem eles, pede `arvore` logo de início."""
        for arquivo in (config.ARQUIVO_ARVORE, config.ARQUIVO_MATRIZ, config.ARQUIVO_METRICAS):
            if not arquivo.exists():
                raise SystemExit(f"Não encontrei {arquivo}.\nRode antes: uv run python -m preditor arvore")

    @staticmethod
    def _exportar(bloco: pd.DataFrame, arvore: Arvore, regras: dict[int, Regra]) -> str:
        """Prevê a validação inteira com a árvore e devolve o texto do JSON (a exportação, sem refazer a árvore)."""
        previsto = ExportadorReplay.prever(bloco, arvore)
        folhas = ExportadorReplay.folhas(bloco, arvore)
        return ExportadorReplay.texto(ExportadorReplay.montar(bloco, previsto, folhas, regras))

    @staticmethod
    def _conferir_com_arvore_oficial(arvore: Arvore) -> None:
        """A árvore refeita tem de ser a que `arvore` gravou; se os hiperparâmetros diferem, o Gold ou o código mudaram."""
        gravada = json.loads(config.ARQUIVO_ARVORE.read_text(encoding="utf-8"))
        if arvore.descricao() != gravada:
            raise SystemExit(
                f"A árvore refeita ({arvore.descricao()}) difere da gravada em {config.ARQUIVO_ARVORE} ({gravada}).\n"
                "Rode antes: uv run python -m preditor arvore"
            )
        print(
            f"Árvore refeita = {config.ARQUIVO_ARVORE.name}: max_depth {gravada['max_depth_pedido']}, "
            f"min_samples_leaf {gravada['min_samples_leaf_pedido']}, {gravada['folhas']} folhas, semente {gravada['semente']}"
        )

    @staticmethod
    def _verificar_antes_de_gravar(dados: DadosModelo, bloco: pd.DataFrame, arvore: Arvore) -> None:
        """Confere, ainda em memória, que as linhas conferíveis são exatamente as da validação que a árvore mediu."""
        validacao = config.BLOCO_VALIDACAO
        conferiveis = bloco.index[bloco["conferivel"]]
        # O índice de cada linha é o do Parquet: o mesmo conjunto de linhas, não só o mesmo número delas.
        assert conferiveis.sort_values().equals(dados.y[validacao].index.sort_values()), (
            "as medições conferíveis não são as linhas da validação do DadosModelo"
        )
        assert len(conferiveis) == dados.resumo[validacao]["n"], (
            f"{len(conferiveis)} conferíveis, mas o N da validação é {dados.resumo[validacao]['n']}"
        )
        # A previsão exportada é a mesma que a árvore dá às linhas medidas em `arvore`.
        exportada = ExportadorReplay.prever(bloco, arvore).loc[dados.X[validacao].index]
        assert exportada.equals(arvore.prever(dados.X[validacao])), "a previsão exportada difere da da árvore oficial"
        # O futuro exportado das conferíveis é o alvo que a árvore usou.
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
    def _verificar_x_e_folhas(
        documento: dict, bloco: pd.DataFrame, arvore: Arvore, dados: DadosModelo, regras: dict[int, Regra]
    ) -> None:
        """V6: `x`, `folha` e `regras` do arquivo. O X tem só as 8 colunas, o ausente continua nulo e cada folha tem regra."""
        medicoes, textos = documento["medicoes"], documento["regras"]
        modelo = arvore.modelo

        # As colunas do documento são as 8 da árvore, na ordem, e nenhuma é proibida (a página não tem nome fixo).
        assert documento["colunas"] == config.COLUNAS_ARVORE, "`colunas` do JSON difere de COLUNAS_ARVORE"
        assert not set(documento["colunas"]) & set(config.COLUNAS_PROIBIDAS), "coluna proibida em `colunas`"
        assert list(modelo.feature_names_in_) == documento["colunas"], "`colunas` difere das colunas com que a árvore foi treinada"

        # Cada `x` tem exatamente 8 valores. Ausente = `null` e nunca vira número (RFC §8.3): o nº de nulos por coluna
        # no JSON é o de `NaN` do Gold, na mesma validação.
        assert all(len(m["x"]) == len(config.COLUNAS_ARVORE) for m in medicoes), "`x` com número de valores diferente de 8"
        no_json = pd.DataFrame([m["x"] for m in medicoes], columns=documento["colunas"], dtype="float64")  # null → NaN
        nulos_do_gold = bloco[config.COLUNAS_ARVORE].isna().sum()
        assert (no_json.isna().sum() == nulos_do_gold).all(), (
            f"nulos por coluna: JSON {no_json.isna().sum().to_dict()} ≠ Gold {nulos_do_gold.to_dict()}"
        )
        # O arredondamento só corta casas: nenhum valor muda mais que meia unidade da última casa.
        # O JSON está em ordem de (`t`, `fluxo_id`), a mesma de `ExportadorReplay.montar`: compara-se por posição.
        ordem = bloco.sort_values(["t", "fluxo_id"], kind="stable")
        exato = ordem[config.COLUNAS_ARVORE].to_numpy(dtype="float64")
        assert np.nanmax(np.abs(no_json.to_numpy() - exato)) <= 0.5 * 10**-config.CASAS_X_REPLAY + 1e-12, "x arredondado difere do exato"

        # A folha do JSON é a que `apply` dá ao X EXATO e também ao X ARREDONDADO que a página mostra.
        folhas = pd.Series([m["folha"] for m in medicoes])
        assert (modelo.apply(no_json) == folhas.to_numpy()).all(), "o x arredondado cai em outra folha que a gravada"
        assert (modelo.apply(ordem[config.COLUNAS_ARVORE].astype("float64")) == folhas.to_numpy()).all(), (
            "a `folha` do JSON difere do `apply` da árvore oficial"
        )

        # Toda folha usada tem regra, a regra cita só colunas permitidas e a classe dela é o `previsto` da medição.
        assert all(str(m["folha"]) in textos for m in medicoes), "folha do JSON sem regra em `regras`"
        for medicao in medicoes:
            assert textos[str(medicao["folha"])].endswith(f" então {medicao['previsto']}"), (
                f"a regra da folha {medicao['folha']} não prevê {medicao['previsto']}"
            )
        estrutura = modelo.tree_
        folhas_da_arvore = {f for f in range(estrutura.node_count) if estrutura.children_left[f] == -1}
        assert {int(f) for f in textos} == folhas_da_arvore, "`regras` não tem exatamente uma regra por folha da árvore"
        assert set(regras) == folhas_da_arvore and all(textos[str(f)] == r.texto() for f, r in regras.items()), (
            "o texto de `regras` difere de `Regra.texto()` da folha"
        )

        # Cada regra, lida como texto (limiar impresso), seleciona exatamente as linhas que `apply` põe na folha dela,
        # no treino e na validação: a frase que a página mostra é a decisão real da árvore.
        for bloco_do_modelo in BLOCOS_USADOS:
            X = dados.X[bloco_do_modelo]
            na_folha = modelo.apply(X)
            for folha, regra in regras.items():
                assert np.array_equal(Regras.selecionar(regra.fundidas, X, limiar_impresso=True), na_folha == folha), (
                    f"{bloco_do_modelo}: a regra da folha {folha} não seleciona as linhas dessa folha"
                )

        # As 3 regras que `arvore` imprime (`Regras.ler`) são as mesmas frases deste documento e estão no arquivo oficial.
        oficiais = Regras.ler(modelo, dados)
        arquivo = config.ARQUIVO_REGRAS.read_text(encoding="utf-8")
        for oficial in oficiais:
            assert textos[str(oficial.folha)] == oficial.texto(), f"regra da folha {oficial.folha} difere de `Regras.ler`"
            assert oficial.texto() in arquivo, f"a regra da folha {oficial.folha} não está em {config.ARQUIVO_REGRAS.name}"
        print(
            f"X e folhas: 8 colunas = COLUNAS_ARVORE, nenhuma proibida | nulos por coluna = Gold {nulos_do_gold.to_dict()} | "
            f"{len(folhas_da_arvore)} folhas, todas com regra (= classe prevista; seleciona as linhas da folha) | "
            f"{len(oficiais)} regras de `arvore` iguais às do arquivo"
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
        """Recalcula matriz e F1 macro só com o JSON (conferíveis) e compara com os CSVs que `arvore` gravou."""
        matriz_csv = pd.read_csv(config.ARQUIVO_MATRIZ)
        metricas_csv = pd.read_csv(config.ARQUIVO_METRICAS)

        conferiveis = pd.DataFrame([m for m in documento["medicoes"] if m["conferivel"]])
        colunas = [f"previsto_{classe}" for classe in config.CLASSES]
        # Cada modelo é lido de uma coluna do JSON: a árvore, de `previsto`; a persistência, de `atual`.
        for modelo, coluna in ((config.MODELO_ARVORE, "previsto"), (config.MODELO_PERSISTENCIA, "atual")):
            resultado = Avaliacao.medir(conferiveis["futuro"], conferiveis[coluna], bloco=config.BLOCO_REPLAY)

            esperada = matriz_csv[matriz_csv["modelo"] == modelo].set_index("verdadeiro").loc[list(config.CLASSES), colunas]
            assert (resultado.matriz.to_numpy() == esperada.to_numpy()).all(), (
                f"{modelo}: a matriz recalculada do JSON difere de {config.ARQUIVO_MATRIZ.name}"
            )
            f1_csv = metricas_csv[(metricas_csv["modelo"] == modelo) & (metricas_csv["metrica"] == "f1_macro")]["valor"].item()
            # O CSV tem o F1 arredondado a `CASAS_CSV` casas: aceita até meia unidade da última casa.
            assert abs(resultado.f1_macro - f1_csv) <= 0.5 * 10**-config.CASAS_CSV, (
                f"{modelo}: F1 macro do JSON {resultado.f1_macro:.6f} difere do CSV {f1_csv:.6f}"
            )
            acertos = int(resultado.matriz.to_numpy().diagonal().sum())
            print(f"  {modelo:<14} F1 macro {resultado.f1_macro:.4f} = CSV | acertos {acertos} de {resultado.n}")
        print("Matriz e F1 macro recalculados do JSON = matriz_validacao.csv e metricas_validacao.csv")

    @staticmethod
    def _verificar_determinismo(bloco: pd.DataFrame, arvore: Arvore, regras: dict[int, Regra], texto: str) -> None:
        """Mesma árvore e mesma entrada = mesmo JSON: refaz só a exportação e compara byte a byte."""
        # A árvore em si já foi conferida contra `arvore_oficial.json` e contra os CSVs; refazer a busca não acrescenta nada.
        assert ExecucaoReplay._exportar(bloco, arvore, regras) == texto, "exportar duas vezes deu um arquivo diferente"
        print(f"Mesma entrada = mesmo JSON (sha256 {hashlib.sha256(texto.encode('utf-8')).hexdigest()[:16]})")
