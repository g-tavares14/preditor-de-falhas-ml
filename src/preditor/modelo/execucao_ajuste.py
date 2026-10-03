"""Orquestra a árvore ajustada da Tarefa 4: busca, compara, verifica e só então grava (SPEC-ajuste-arvore.md).

Roda sem Spark e sem Java, como o `arvore`. Mede quatro modelos nas mesmas linhas da validação: a persistência, a
árvore da Tarefa 3 (refeita e conferida contra o que o `arvore` gravou) e as duas variantes da ajustada (sem e com
peso de classe). Os arquivos da Tarefa 3 não são reescritos.
"""

import json

import pandas as pd

from preditor import config
from preditor.modelo.ajuste import COMBINACAO, ArvoreAjustada
from preditor.modelo.arvore import Arvore
from preditor.modelo.avaliacao import Avaliacao, Mudanca, Resultado
from preditor.modelo.dados import BLOCOS_USADOS, DadosModelo
from preditor.modelo.execucao import ExecucaoArvore
from preditor.modelo.regras import Regra, Regras

# As transições (agora → futuro) que a saída destaca: são os erros que o diário da Tarefa 4 pede para citar.
TRANSICOES_DESTAQUE = [("FALHA", "OK"), ("OK", "RISCO"), ("RISCO", "OK"), ("OK", "FALHA")]


class ExecucaoAjuste:
    def executar(self) -> None:
        # Sem o Gold (ou com um Gold sem as colunas novas), `DadosModelo` diz qual comando rodar antes.
        dados = DadosModelo().carregar()
        self._exigir_tarefa_3()
        validacao = config.BLOCO_VALIDACAO
        verdadeiro = dados.y[validacao]
        self._imprimir_dados(dados)

        # Os quatro modelos, nas mesmas linhas: `previstos` guarda a classe prevista de cada um.
        previstos = {config.MODELO_PERSISTENCIA: dados.status_atual_validacao}

        # Árvore da Tarefa 3: refeita aqui (mesma semente) só para ser medida ao lado; o `arvore` é quem a grava.
        tarefa_3 = Arvore().buscar(dados)
        previstos[config.MODELO_ARVORE] = tarefa_3.prever(dados.X[validacao])

        # As duas variantes da ajustada: mesma grade e mesma regra de escolha, sem e com peso de classe.
        variantes = {nome: ArvoreAjustada(nome, peso).buscar(dados) for nome, peso in config.VARIANTES_AJUSTE.items()}
        for nome, variante in variantes.items():
            previstos[nome] = variante.prever_bloco(dados, validacao)
        ajustada = variantes[config.MODELO_AJUSTADA]

        # As mesmas contas para todos: matriz e métricas, acerto quando o futuro muda e F1 por região.
        resultados = {m: Avaliacao.medir(verdadeiro, p, bloco=validacao) for m, p in previstos.items()}
        mudancas = {
            m: Avaliacao.quando_muda(verdadeiro, p, dados.status_atual_validacao, bloco=validacao)
            for m, p in previstos.items()
        }
        regioes = {m: Avaliacao.por_regiao(verdadeiro, p, dados.regiao_validacao, bloco=validacao) for m, p in previstos.items()}

        # Regras em português da ajustada, lidas com o X dela (as 10 colunas).
        x_ajustado = {bloco: dados.x_ajustado(bloco) for bloco in BLOCOS_USADOS}
        regras = Regras.ler(ajustada.modelo, dados, x_ajustado, casas=config.CASAS_LIMIAR_REGRA_AJUSTE)

        # Tudo é conferido antes de gravar ou imprimir resultado: uma checagem que falha não deixa arquivo novo.
        self._verificar_tarefa_3(tarefa_3, resultados[config.MODELO_ARVORE])
        for variante in variantes.values():
            variante.verificar(dados)
        Regras.verificar(ajustada.modelo, regras, dados, x_ajustado)
        # A persistência acerta tudo quando o futuro repete o agora e nada quando muda: é a definição dela.
        persistencia = mudancas[config.MODELO_PERSISTENCIA]
        assert persistencia.acerto_igual == 1.0 and persistencia.acerto_muda == 0.0, "a persistência não é o `status_atual`"

        self._imprimir_erro_e_mudanca(resultados, mudancas)
        for variante in variantes.values():
            self._imprimir_busca(variante)
        self._imprimir_arvore(ajustada)
        print("\n" + Regras.texto(regras))
        ExecucaoArvore._imprimir_resultado(config.MODELO_AJUSTADA, resultados[config.MODELO_AJUSTADA])
        comparacao = self._quadro_comparacao(resultados, mudancas, tarefa_3, variantes)
        self._imprimir_comparacao(comparacao)
        self._imprimir_transicoes(mudancas)
        self._imprimir_regioes(regioes)

        self._gravar(dados, variantes, ajustada, regras, resultados, mudancas, regioes, comparacao)

    @staticmethod
    def _exigir_tarefa_3() -> None:
        """A comparação é contra o que o `arvore` gravou: sem esses arquivos, pede para rodá-lo antes."""
        for arquivo in (config.ARQUIVO_ARVORE, config.ARQUIVO_METRICAS):
            if not arquivo.exists():
                raise SystemExit(f"Não encontrei {arquivo}.\nRode antes: uv run python -m preditor arvore")

    @staticmethod
    def _verificar_tarefa_3(tarefa_3: Arvore, resultado: Resultado) -> None:
        """A árvore da Tarefa 3 refeita aqui é a que o `arvore` gravou: mesmos parâmetros e mesmas métricas."""
        gravada = json.loads(config.ARQUIVO_ARVORE.read_text(encoding="utf-8"))
        assert tarefa_3.descricao() == gravada, "a árvore da Tarefa 3 refeita difere de arvore_oficial.json"
        assert list(tarefa_3.modelo.feature_names_in_) == config.COLUNAS_ARVORE, "a árvore da Tarefa 3 viu outras colunas"

        gravadas = pd.read_csv(config.ARQUIVO_METRICAS)
        da_arvore = gravadas[gravadas["modelo"] == config.MODELO_ARVORE].reset_index(drop=True)
        refeitas = Avaliacao.quadro_metricas(config.MODELO_ARVORE, resultado)
        assert da_arvore[["metrica", "classe"]].equals(refeitas[["metrica", "classe"]]), "métricas da Tarefa 3 em outra ordem"
        diferenca = (da_arvore["valor"] - refeitas["valor"]).abs().max()
        assert diferenca <= config.TOLERANCIA_METRICA, f"métricas da Tarefa 3 refeitas diferem de metricas_validacao.csv ({diferenca})"

    @staticmethod
    def _imprimir_dados(dados: DadosModelo) -> None:
        colunas = DadosModelo.colunas_ajustadas()
        print("Árvore ajustada (Tarefa 4): mesmo alvo, mesmo corte e mesma folga da Tarefa 3.")
        print(f"Colunas ({len(colunas)}): as {len(config.COLUNAS_ARVORE)} da Tarefa 3 + {', '.join(config.COLUNAS_AJUSTE)}")
        for bloco in BLOCOS_USADOS:
            nulos = dados.extras_ajuste[bloco].isna().sum().to_dict()
            print(f"  {bloco:<10} N = {dados.resumo[bloco]['n']:>6} | ausentes nas colunas novas: {nulos}")
        # Do teste, só o N: fechado até a Tarefa 5.
        print(f"  {config.BLOCO_TESTE:<10} N = {dados.n_teste:>6} | fechado até a Tarefa 5 (nada dele é medido)")

    @staticmethod
    def _acerto_transicao(mudanca: Mudanca, atual: str, futuro: str) -> tuple[int, float]:
        t = mudanca.transicoes
        linha = t[(t["atual"] == atual) & (t["futuro"] == futuro)].iloc[0]
        return int(linha["n"]), float(linha["acerto"])

    @staticmethod
    def _imprimir_erro_e_mudanca(resultados: dict[str, Resultado], mudancas: dict[str, Mudanca]) -> None:
        """A tabela "erro da Tarefa 3 → mudança" do diário (seção 1), com os números medidos agora."""
        t3, m3 = resultados[config.MODELO_ARVORE], mudancas[config.MODELO_ARVORE]
        n_pico, acerto_pico = ExecucaoAjuste._acerto_transicao(m3, "FALHA", "OK")
        previsto_risco, real_risco = int(t3.matriz["RISCO"].sum()), int(t3.matriz.loc["RISCO"].sum())
        peso = ", ".join(f"{classe} {valor:g}" for classe, valor in config.PESO_CLASSES_AJUSTE.items())
        print("\nErro da Tarefa 3 → mudança na árvore (diário da Tarefa 4, seção 1):")
        print(f"  1. Pico isolado virando FALHA: quando o agora é FALHA e o futuro é OK ({n_pico} linhas), a árvore da")
        print(f"     Tarefa 3 acerta {acerto_pico:.1%}.")
        print("     → coluna nova `min5_z` (menor z_robusto das últimas 5 medições: baixo com z alto = pico isolado).")
        print(f"  2. RISCO sumindo: recall de RISCO {t3.por_classe.loc['RISCO', 'recall']:.4f}; a árvore prevê RISCO em")
        print(f"     {previsto_risco} linhas e há {real_risco}.")
        print(f"     → coluna nova `media5_z` (média do z_robusto das últimas 5) e peso de classe ({peso}).")
        print(f"  3. A árvore repete o agora: quando o futuro muda ({m3.n_muda} linhas), acerta {m3.acerto_muda:.1%}.")
        print("     → as duas colunas novas dão o histórico recente do z_robusto.")

    @staticmethod
    def _imprimir_busca(variante: ArvoreAjustada) -> None:
        peso = "sem peso de classe" if variante.peso is None else f"peso {variante.peso}"
        melhor = variante.busca["f1_macro_validacao"].max()
        limite = melhor - config.TOLERANCIA_ESCOLHA
        print(f"\nBusca `{variante.nome}` ({peso}): {len(variante.busca)} árvores treinadas só no treino.")
        print(f"  Maior F1 macro da validação: {melhor:.4f}. Dentro da tolerância de {config.TOLERANCIA_ESCOLHA:g}")
        print(f"  (F1 ≥ {limite:.4f}), da mais simples para a mais complexa; vence a primeira:")
        print(f"  {'critério':<10}{'max_depth':>10}{'min_leaf':>10}{'folhas':>8}{'F1 treino':>11}{'F1 valid.':>11}")
        candidatas = variante.busca[variante.busca["f1_macro_validacao"] >= limite]
        for posicao, linha in ArvoreAjustada.ordem_de_simplicidade(candidatas).iterrows():
            marca = "  <- escolhida" if posicao == variante.posicao_escolhida else ""
            print(
                f"  {linha['criterio']:<10}{int(linha['max_depth']):>10}{int(linha['min_samples_leaf']):>10}"
                f"{int(linha['folhas']):>8}{linha['f1_macro_treino']:>11.4f}{linha['f1_macro_validacao']:>11.4f}{marca}"
            )
        print(f"  (a tabela inteira, com as {len(variante.busca)} combinações, vai para {config.ARQUIVO_BUSCA_AJUSTE.name})")

    @staticmethod
    def _imprimir_arvore(ajustada: ArvoreAjustada) -> None:
        d = ajustada.descricao()
        peso = "sem class_weight" if d["class_weight"] is None else f"class_weight {d['class_weight']}"
        print(f"\nÁrvore ajustada (`{ajustada.nome}`): parâmetros candidatos, ainda não é o teste.")
        print(f"  critério:            {d['criterio']}  (semente {d['semente']}, {peso})")
        print(f"  max_depth pedido:    {d['max_depth_pedido']}")
        print(f"  profundidade obtida: {d['profundidade_obtida']}")
        print(f"  min_samples_leaf:    {d['min_samples_leaf_pedido']}")
        print(f"  folhas:              {d['folhas']}")
        # Importância de cada coluna (soma 1): mostra o quanto as colunas novas pesaram.
        importancias = pd.Series(ajustada.modelo.feature_importances_, index=d["colunas"]).sort_values(ascending=False)
        print("  importância das colunas: " + ", ".join(f"{c} {v:.3f}" for c, v in importancias.items() if v > 0))
        print(f"\n  Divisões dos {config.NIVEIS_DIVISOES} primeiros níveis (N = linhas de treino que chegam ao nó):")
        for linha in ajustada.divisoes_iniciais():
            print(f"    {linha}")

    @staticmethod
    def _quadro_comparacao(
        resultados: dict[str, Resultado], mudancas: dict[str, Mudanca], tarefa_3: Arvore, variantes: dict[str, ArvoreAjustada]
    ) -> pd.DataFrame:
        """A tabela Tarefa 3 → Tarefa 4 do diário (seção 3), mais as folhas e o acerto quando o futuro muda."""
        folhas = {config.MODELO_ARVORE: int(tarefa_3.modelo.tree_.n_leaves)}
        folhas.update({nome: int(v.modelo.tree_.n_leaves) for nome, v in variantes.items()})
        linhas = []
        for modelo, r in resultados.items():
            linhas.append(
                {
                    "modelo": modelo,
                    "folhas": folhas.get(modelo),  # a persistência não é árvore: fica vazio
                    "f1_macro": r.f1_macro,
                    "recall_FALHA": r.por_classe.loc["FALHA", "recall"],
                    "recall_RISCO": r.por_classe.loc["RISCO", "recall"],
                    "acerto_futuro_muda": mudancas[modelo].acerto_muda,
                }
            )
        quadro = pd.DataFrame(linhas)
        quadro["folhas"] = quadro["folhas"].astype("Int64")  # inteiro que aceita vazio
        return quadro

    @staticmethod
    def _imprimir_comparacao(comparacao: pd.DataFrame) -> None:
        print(f"\nTarefa 3 → Tarefa 4 na validação (a adotada é `{config.MODELO_AJUSTADA}`):")
        print(f"  {'modelo':<20}{'folhas':>8}{'F1 macro':>10}{'rec. FALHA':>12}{'rec. RISCO':>12}{'futuro muda':>13}")
        for linha in comparacao.itertuples():
            folhas = "" if pd.isna(linha.folhas) else str(linha.folhas)
            print(
                f"  {linha.modelo:<20}{folhas:>8}{linha.f1_macro:>10.4f}{linha.recall_FALHA:>12.4f}"
                f"{linha.recall_RISCO:>12.4f}{linha.acerto_futuro_muda:>13.1%}"
            )
        # A leitura do ganho, como saiu: sem trocar alvo nem rótulo se não houver ganho.
        por_modelo = comparacao.set_index("modelo")
        t3, t4 = por_modelo.loc[config.MODELO_ARVORE], por_modelo.loc[config.MODELO_AJUSTADA]
        for nome, coluna in (("F1 macro", "f1_macro"), ("recall de FALHA", "recall_FALHA"), ("recall de RISCO", "recall_RISCO")):
            diferenca = t4[coluna] - t3[coluna]
            veredito = "sobe" if diferenca > 0 else "cai" if diferenca < 0 else "não muda"
            print(f"  Ajustada − Tarefa 3, {nome}: {diferenca:+.4f} ({veredito}).")

    @staticmethod
    def _imprimir_transicoes(mudancas: dict[str, Mudanca]) -> None:
        print("\nAcerto por transição (agora → futuro) na validação:")
        print(f"  {'transição':<16}{'N':>7}" + "".join(f"{modelo:>20}" for modelo in mudancas))
        for atual, futuro in TRANSICOES_DESTAQUE:
            n = ExecucaoAjuste._acerto_transicao(next(iter(mudancas.values())), atual, futuro)[0]
            acertos = "".join(f"{ExecucaoAjuste._acerto_transicao(m, atual, futuro)[1]:>20.1%}" for m in mudancas.values())
            print(f"  {atual + ' → ' + futuro:<16}{n:>7}{acertos}")

    @staticmethod
    def _imprimir_regioes(regioes: dict[str, pd.DataFrame]) -> None:
        print("\nF1 macro por região de destino na validação (a região só agrupa: nenhum modelo a viu):")
        print(f"  {'região':<18}{'N':>7}" + "".join(f"{modelo:>20}" for modelo in regioes))
        primeiro = next(iter(regioes.values()))
        for posicao, linha in primeiro.iterrows():
            valores = "".join(f"{quadro.loc[posicao, 'f1_macro']:>20.4f}" for quadro in regioes.values())
            print(f"  {linha['regiao']:<18}{int(linha['n']):>7}{valores}")

    @staticmethod
    def _gravar(
        dados: DadosModelo,
        variantes: dict[str, ArvoreAjustada],
        ajustada: ArvoreAjustada,
        regras: list[Regra],
        resultados: dict[str, Resultado],
        mudancas: dict[str, Mudanca],
        regioes: dict[str, pd.DataFrame],
        comparacao: pd.DataFrame,
    ) -> None:
        """Grava os arquivos do ajuste (nenhum da Tarefa 3) e confere o que foi para o disco."""
        config.MODELO.mkdir(parents=True, exist_ok=True)
        n_validacao = dados.resumo[config.BLOCO_VALIDACAO]["n"]

        busca = pd.concat([v.quadro_busca() for v in variantes.values()], ignore_index=True)
        busca.to_csv(config.ARQUIVO_BUSCA_AJUSTE, index=False)
        descricao = ajustada.descricao()
        config.ARQUIVO_ARVORE_AJUSTADA.write_text(json.dumps(descricao, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        texto = ajustada.regras_texto() + "\n" + Regras.texto(regras)
        config.ARQUIVO_REGRAS_AJUSTADA.write_text(texto, encoding="utf-8")

        matriz = pd.concat([Avaliacao.quadro_matriz(m, r) for m, r in resultados.items()], ignore_index=True)
        matriz.to_csv(config.ARQUIVO_MATRIZ_AJUSTE, index=False)
        # As métricas de sempre (com o N medido ao lado) e, depois, as da Tarefa 4 (cada uma com o N do grupo).
        classicas = pd.concat([Avaliacao.quadro_metricas(m, r).assign(n=r.n) for m, r in resultados.items()], ignore_index=True)
        extras = pd.concat([Avaliacao.quadro_extras(m, mudancas[m], regioes[m]) for m in resultados], ignore_index=True)
        pd.concat([classicas, extras], ignore_index=True).to_csv(config.ARQUIVO_METRICAS_AJUSTE, index=False)
        comparacao.round(config.CASAS_CSV).to_csv(config.ARQUIVO_COMPARACAO, index=False)

        print()
        arquivos = (
            config.ARQUIVO_BUSCA_AJUSTE, config.ARQUIVO_ARVORE_AJUSTADA, config.ARQUIVO_REGRAS_AJUSTADA,
            config.ARQUIVO_MATRIZ_AJUSTE, config.ARQUIVO_METRICAS_AJUSTE, config.ARQUIVO_COMPARACAO,
        )
        for arquivo in arquivos:
            print(f"Gravado: {arquivo}")

        ExecucaoAjuste._verificar_disco(variantes, ajustada, descricao, texto, resultados, n_validacao)

    @staticmethod
    def _verificar_disco(
        variantes: dict[str, ArvoreAjustada],
        ajustada: ArvoreAjustada,
        descricao: dict,
        texto: str,
        resultados: dict[str, Resultado],
        n_validacao: int,
    ) -> None:
        """Checagens sobre o que foi gravado: é o que o dono lê e o que a Tarefa 5 vai usar."""
        casa = 10**-config.CASAS_CSV  # o CSV arredonda: uma unidade da última casa de folga

        # Busca: cada variante com a grade inteira, uma escolhida, e a regra de escolha refeita a partir do CSV.
        busca = pd.read_csv(config.ARQUIVO_BUSCA_AJUSTE)
        assert set(busca["modelo"]) == set(variantes), f"variantes em busca_ajuste.csv: {sorted(set(busca['modelo']))}"
        for nome, variante in variantes.items():
            da_variante = busca[busca["modelo"] == nome].reset_index(drop=True)
            assert da_variante[COMBINACAO].equals(variante.busca[COMBINACAO]), f"{nome}: busca gravada em outra ordem"
            assert da_variante["escolhida"].sum() == 1, f"{nome}: a busca gravada precisa ter exatamente uma escolhida"
            escolhida = da_variante[da_variante["escolhida"]].iloc[0]
            limite = da_variante["f1_macro_validacao"].max() - config.TOLERANCIA_ESCOLHA
            assert escolhida["f1_macro_validacao"] >= limite - casa, f"{nome}: a escolhida gravada está fora da tolerância"
            # Nenhuma árvore antes dela, na ordem de simplicidade, está dentro da tolerância.
            ordenada = ArvoreAjustada.ordem_de_simplicidade(da_variante).reset_index(drop=True)
            antes = ordenada.iloc[: int(ordenada["escolhida"].idxmax())]
            assert (antes["f1_macro_validacao"] < limite + casa).all(), f"{nome}: árvore mais simples dentro da tolerância"
            pedido = (escolhida["criterio"], escolhida["max_depth"], escolhida["min_samples_leaf"])
            assert pedido == (variante.criterio, variante.profundidade_pedida, variante.folha_minima), (
                f"{nome}: a escolhida gravada não é a árvore treinada"
            )
            # A escolhida, medida fora da busca, tem o F1 macro da linha dela: é a mesma árvore.
            assert abs(escolhida["f1_macro_validacao"] - resultados[nome].f1_macro) <= casa, f"{nome}: F1 da busca ≠ F1 medido"

        # JSON e regras: o que está no disco é o que foi gerado, e só cita as 10 colunas e as 3 classes.
        gravado = json.loads(config.ARQUIVO_ARVORE_AJUSTADA.read_text(encoding="utf-8"))
        assert gravado == descricao, "arvore_ajustada.json diferente da árvore treinada"
        assert gravado["modelo"] == config.MODELO_AJUSTADA, "arvore_ajustada.json não é da variante adotada"
        assert gravado["colunas"] == config.COLUNAS_ARVORE + config.COLUNAS_AJUSTE, "arvore_ajustada.json com outras colunas"
        no_disco = config.ARQUIVO_REGRAS_AJUSTADA.read_text(encoding="utf-8")
        assert no_disco == texto, "regras_arvore_ajustada.txt diferente do que foi gerado"
        ArvoreAjustada.verificar_regras(no_disco, permitidas=gravado["colunas"])

        # Matriz: os quatro modelos, cada um somando o N da validação.
        matriz = pd.read_csv(config.ARQUIVO_MATRIZ_AJUSTE)
        colunas = [f"previsto_{classe}" for classe in config.CLASSES]
        assert set(matriz["modelo"]) == set(resultados), f"modelos em matriz_ajuste.csv: {sorted(set(matriz['modelo']))}"
        somas = matriz.groupby("modelo")[colunas].sum().sum(axis=1)
        assert (somas == n_validacao).all(), f"matriz_ajuste.csv não soma o N da validação ({n_validacao}): {dict(somas)}"

        # Métricas: F1 macro = média dos 3 F1; regiões e os dois grupos (futuro igual / muda) somam o N.
        metricas = pd.read_csv(config.ARQUIVO_METRICAS_AJUSTE)
        assert set(metricas["modelo"]) == set(resultados), "modelos em metricas_ajuste.csv"
        for modelo in resultados:
            do_modelo = metricas[metricas["modelo"] == modelo]

            def valores(metrica: str) -> pd.DataFrame:
                return do_modelo[do_modelo["metrica"] == metrica]

            f1_macro = valores("f1_macro")["valor"].iloc[0]
            assert abs(f1_macro - valores("f1")["valor"].mean()) <= casa, f"{modelo}: f1_macro gravado ≠ média dos 3 f1"
            assert valores("f1_macro_regiao")["n"].sum() == n_validacao, f"{modelo}: as regiões gravadas não somam o N"
            assert valores("acerto_transicao")["n"].sum() == n_validacao, f"{modelo}: as transições gravadas não somam o N"
            grupos = valores("acerto_futuro_igual")["n"].iloc[0] + valores("acerto_futuro_muda")["n"].iloc[0]
            assert grupos == n_validacao, f"{modelo}: futuro igual + futuro muda gravados ≠ N"

        # Tabela do diário: as mesmas quatro linhas, com o F1 macro e os recalls das métricas gravadas.
        comparacao = pd.read_csv(config.ARQUIVO_COMPARACAO).set_index("modelo")
        assert list(comparacao.index) == list(resultados), "comparacao_t3_t4.csv com outros modelos"
        for modelo, r in resultados.items():
            assert abs(comparacao.loc[modelo, "f1_macro"] - r.f1_macro) <= casa, f"{modelo}: F1 macro da comparação"
            for classe in ("FALHA", "RISCO"):
                assert abs(comparacao.loc[modelo, f"recall_{classe}"] - r.por_classe.loc[classe, "recall"]) <= casa, (
                    f"{modelo}: recall de {classe} da comparação"
                )
        assert comparacao.loc[config.MODELO_AJUSTADA, "folhas"] == ajustada.modelo.tree_.n_leaves, "folhas da ajustada"
