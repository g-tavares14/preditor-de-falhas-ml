"""Orquestra a árvore: lê o Gold, prepara X e y, imprime e verifica (SPEC-arvore.md).

Roda sem Spark e sem Java: só pandas + scikit-learn sobre o Parquet do Gold.
"""

import json

import pandas as pd

from preditor import config
from preditor.modelo.arvore import Arvore, ArvoreContraste
from preditor.modelo.avaliacao import Avaliacao, ErroConcreto, Resultado
from preditor.modelo.dados import BLOCOS_USADOS, DadosModelo
from preditor.modelo.regras import Regra, Regras


class ExecucaoArvore:
    def executar(self) -> None:
        # Sem o Gold no disco, `DadosModelo` termina com a mensagem de qual comando rodar antes.
        dados = DadosModelo().carregar()
        self._imprimir_dados(dados)

        # Régua de comparação: a persistência prevê que o futuro é igual ao agora (`status_atual`), nas
        # mesmas linhas da validação que a árvore usará (depois da folga e do filtro de futuro nulo).
        # Ela vem antes de qualquer árvore: o dono vê o número a bater (RFC §9).
        verdadeiro = dados.y[config.BLOCO_VALIDACAO]
        resultados = {
            config.MODELO_PERSISTENCIA: Avaliacao.medir(
                verdadeiro, dados.status_atual_validacao, bloco=config.BLOCO_VALIDACAO
            )
        }
        self._imprimir_resultado(config.MODELO_PERSISTENCIA, resultados[config.MODELO_PERSISTENCIA])

        # Árvore oficial: 28 árvores treinadas só no treino; a validação escolhe uma (ver `Arvore.buscar`).
        arvore = Arvore().buscar(dados)
        self._imprimir_busca(arvore)
        self._imprimir_arvore(arvore)

        # A escolhida é medida de novo, fora da busca, com a mesma função de métricas da persistência.
        previsto = arvore.prever(dados.X[config.BLOCO_VALIDACAO])
        resultados[config.MODELO_ARVORE] = Avaliacao.medir(verdadeiro, previsto, bloco=config.BLOCO_VALIDACAO)
        self._imprimir_resultado(config.MODELO_ARVORE, resultados[config.MODELO_ARVORE])
        self._imprimir_comparacao(resultados)

        # Leitura da árvore: 3 regras em português, a partir do caminho real raiz → folha.
        regras = Regras.ler(arvore.modelo, dados)
        print("\n" + Regras.texto(regras))

        # Leitura do erro: dois casos concretos da validação. `fluxo_id`, `t`, `rtt` e a mediana só localizam
        # e classificam a linha (vêm por um caminho à parte); a árvore nunca os viu.
        erros = Avaliacao.erros_concretos(
            dados.X[config.BLOCO_VALIDACAO],
            verdadeiro,
            previsto,
            dados.status_atual_validacao,
            dados.localizacao_validacao,
            dados.mediana_das_medianas,
        )
        self._imprimir_erros(erros, dados.mediana_das_medianas)

        # Árvore de contraste: NÃO é o modelo do projeto. Mesmo treino, alvo e hiperparâmetros da oficial, com
        # `rtt` e região. A estrutura da oficial é guardada antes para provar, no fim, que o contraste não a tocou.
        estrutura_oficial = arvore.estrutura()
        contraste = ArvoreContraste().treinar(arvore, dados)
        previsto_contraste = contraste.prever(dados.x_contraste(config.BLOCO_VALIDACAO))
        resultados[config.MODELO_CONTRASTE] = Avaliacao.medir(
            verdadeiro, previsto_contraste, bloco=config.BLOCO_VALIDACAO
        )
        self._imprimir_contraste(contraste, dados, resultados)

        # O N da validação vem da A1 (`DadosModelo.resumo`), não de um `len` do mesmo `y` que foi medido.
        self._gravar_avaliacao(resultados, n_validacao=dados.resumo[config.BLOCO_VALIDACAO]["n"])
        self._gravar_arvore(arvore, dados, resultados[config.MODELO_ARVORE], regras)
        self._gravar_contraste(contraste, arvore, dados, estrutura_oficial)

    @staticmethod
    def _imprimir_dados(dados: DadosModelo) -> None:
        print(f"Alvo: {config.ALVO} (a classe do mesmo fluxo {config.PASSOS_FUTURO} medições à frente)")
        print(f"Colunas da árvore ({len(config.COLUNAS_ARVORE)}): {', '.join(config.COLUNAS_ARVORE)}")

        # Quantas linhas saíram de cada bloco, e por quê (a folga é explicada em `DadosModelo._marcar_folga`).
        print(f"\nLinhas removidas (folga = as {config.PASSOS_FUTURO} últimas medições de cada fluxo, RFC §9):")
        print(f"  {'bloco':<10}{'linhas':>8}{'futuro nulo':>13}{'folga':>8}{'N':>8}")
        for bloco in BLOCOS_USADOS:
            r = dados.resumo[bloco]
            print(f"  {bloco:<10}{r['linhas']:>8}{r['futuro_nulo']:>13}{r['folga']:>8}{r['n']:>8}")
        # Do teste, só o N: nenhuma outra conta com ele até a Tarefa 5.
        print(f"  {config.BLOCO_TESTE:<10}{'':>8}{'':>13}{'':>8}{dados.n_teste:>8}")

        print("\nN por bloco e classe (alvo):")
        print(f"  {'bloco':<10}" + "".join(f"{classe:>8}" for classe in config.CLASSES) + f"{'total':>8}")
        for bloco in BLOCOS_USADOS:
            contagem = dados.y[bloco].value_counts()
            print(
                f"  {bloco:<10}"
                + "".join(f"{contagem[classe]:>8}" for classe in config.CLASSES)
                + f"{len(dados.y[bloco]):>8}"
            )
        print(f"  {config.BLOCO_TESTE:<10}  só o N, acima (fechado até a Tarefa 5)")

    @staticmethod
    def _imprimir_resultado(modelo: str, r: Resultado) -> None:
        print(f"\nValidação, modelo `{modelo}` (N = {r.n}):")

        # Matriz em contagem: cada linha é a classe verdadeira, cada coluna a classe prevista.
        print("  Matriz (linha = verdadeiro, coluna = previsto):")
        print(f"  {'verdadeiro':<12}" + "".join(f"{classe:>8}" for classe in config.CLASSES) + f"{'total':>8}")
        for classe, linha in r.matriz.iterrows():
            print(f"  {classe:<12}" + "".join(f"{v:>8}" for v in linha) + f"{linha.sum():>8}")

        print("  Por classe:")
        print(f"  {'classe':<12}{'precisão':>10}{'recall':>10}{'F1':>10}{'N':>8}")
        for classe, m in r.por_classe.iterrows():
            print(f"  {classe:<12}{m['precisao']:>10.4f}{m['recall']:>10.4f}{m['f1']:>10.4f}{int(m['suporte']):>8}")

        print(f"  F1 macro:          {r.f1_macro:.4f}  (média dos 3 F1: é a métrica que decide)")
        print(f"  Balanced accuracy: {r.balanced_accuracy:.4f}  (média dos 3 recalls)")
        print(f"  Acurácia:          {r.acuracia:.4f}  ({r.acuracia:.1%}; só informativa, não decide nada: OK é a maioria)")

    @staticmethod
    def _gravar_avaliacao(resultados: dict[str, Resultado], n_validacao: int) -> None:
        """Grava matriz e métricas de todos os modelos medidos, um modelo por grupo de linhas."""
        # A pasta não existe antes da primeira execução (as saídas ficam fora do git).
        config.MODELO.mkdir(parents=True, exist_ok=True)

        # Cada modelo é um grupo de linhas com o nome na coluna `modelo`: persistência, árvore oficial e contraste.
        matriz = pd.concat([Avaliacao.quadro_matriz(m, r) for m, r in resultados.items()], ignore_index=True)
        metricas = pd.concat([Avaliacao.quadro_metricas(m, r) for m, r in resultados.items()], ignore_index=True)
        matriz.to_csv(config.ARQUIVO_MATRIZ, index=False)
        metricas.to_csv(config.ARQUIVO_METRICAS, index=False)
        print(f"\nGravado: {config.ARQUIVO_MATRIZ}")
        print(f"Gravado: {config.ARQUIVO_METRICAS}")

        # Verificação do que foi para o disco: cada modelo da matriz soma o N da validação.
        lida = pd.read_csv(config.ARQUIVO_MATRIZ)
        colunas = [f"previsto_{classe}" for classe in config.CLASSES]
        assert set(lida["modelo"]) == set(resultados), f"modelos no CSV: {sorted(set(lida['modelo']))}"
        somas = lida.groupby("modelo")[colunas].sum().sum(axis=1)
        assert (somas == n_validacao).all(), f"a matriz gravada não soma o N da validação ({n_validacao}): {dict(somas)}"

        # As métricas gravadas, de cada modelo: o `f1_macro` é a média dos 3 `f1` por classe.
        lidas = pd.read_csv(config.ARQUIVO_METRICAS)
        assert set(lidas["modelo"]) == set(resultados), f"modelos no CSV de métricas: {sorted(set(lidas['modelo']))}"
        f1_por_classe = lidas[lidas["metrica"] == "f1"].groupby("modelo")["valor"]
        assert (f1_por_classe.count() == len(config.CLASSES)).all(), "cada modelo precisa de 3 `f1` por classe"
        f1_macro = lidas[lidas["metrica"] == "f1_macro"].set_index("modelo")["valor"]
        # Cada valor foi arredondado a `CASAS_CSV` casas (erro de até meia unidade da última casa): a
        # diferença entre o `f1_macro` e a média pode chegar a uma unidade dela.
        tolerancia = 10**-config.CASAS_CSV + config.TOLERANCIA_METRICA
        diferenca = (f1_macro - f1_por_classe.mean()).abs()
        assert (diferenca <= tolerancia).all(), f"`f1_macro` gravado ≠ média dos 3 `f1` gravados: {dict(diferenca)}"

    @staticmethod
    def _imprimir_busca(arvore: Arvore) -> None:
        total = len(arvore.busca)
        print(f"\nBusca de hiperparâmetros: {total} árvores treinadas só no treino, medidas na validação.")
        print("  Escolha: maior F1 macro na validação; empate → menor max_depth, depois maior min_samples_leaf.")
        print(f"  {'max_depth':>10}{'min_leaf':>10}{'obtida':>8}{'folhas':>8}{'F1 treino':>11}{'F1 valid.':>11}")
        for posicao, linha in arvore.busca.iterrows():
            marca = "  <- escolhida" if posicao == 0 else ""
            print(
                f"  {int(linha['max_depth']):>10}{int(linha['min_samples_leaf']):>10}"
                f"{int(linha['profundidade_obtida']):>8}{int(linha['folhas']):>8}"
                f"{linha['f1_macro_treino']:>11.4f}{linha['f1_macro_validacao']:>11.4f}{marca}"
            )

    @staticmethod
    def _imprimir_arvore(arvore: Arvore) -> None:
        d = arvore.descricao()
        print("\nÁrvore oficial:")
        print(f"  critério:            {d['criterio']}  (semente {d['semente']}, sem class_weight)")
        print(f"  max_depth pedido:    {d['max_depth_pedido']}")
        print(f"  profundidade obtida: {d['profundidade_obtida']}")
        print(f"  min_samples_leaf:    {d['min_samples_leaf_pedido']}")
        print(f"  folhas:              {d['folhas']}")
        print(f"\n  Divisões dos {config.NIVEIS_DIVISOES} primeiros níveis (N = linhas de treino que chegam ao nó):")
        for linha in arvore.divisoes_iniciais():
            print(f"    {linha}")

    @staticmethod
    def _imprimir_erros(erros: list[ErroConcreto], mediana_das_medianas: float) -> None:
        """Os erros concretos da validação, prontos para colar no diário: ou a linha, ou "não apareceu"."""
        print(f"Erros concretos da árvore na validação (verdadeiro = {config.ALVO}; previsto = árvore oficial):")
        for numero, erro in enumerate(erros, start=1):
            print(f"\n  Erro {numero}: {erro.caso.titulo}")
            print(f"    critério: {erro.caso.descricao(mediana_das_medianas)}")
            if erro.linha is None:
                # Nada de afrouxar o critério nem de inventar um exemplo.
                print("    não apareceu na validação (nenhuma linha atende ao critério).")
                continue
            linha = erro.linha
            print(f"    {erro.candidatos} linhas da validação atendem ao critério; esta é a primeira da lista ordenada.")
            print(f"    fluxo_id:        {linha['fluxo_id']}")
            print(f"    t:               {linha['t']}")  # como texto, sem formatar o fuso
            print(f"    rtt:             {linha['rtt']:.2f} ms")
            print(f"    mediana do fluxo: {linha[config.COLUNA_MEDIANA_FLUXO]:.2f} ms (baseline do Período A)")
            print("    métricas (as 8 colunas da árvore):")
            for coluna in config.COLUNAS_ARVORE:
                valor = linha[coluna]
                # Valor ausente fica ausente (RFC §8.3): aparece como tal, não como 0.
                print(f"      {coluna:<16}{'ausente' if pd.isna(valor) else f'{valor:.4g}'}")
            print(f"    status_atual:    {linha['status_atual']}")
            print(f"    classe verdadeira ({config.ALVO}): {linha['verdadeiro']}")
            print(f"    classe prevista (árvore):          {linha['previsto']}")

    @staticmethod
    def _imprimir_comparacao(resultados: dict[str, Resultado]) -> None:
        """Árvore × persistência lado a lado, na mesma validação e com as mesmas métricas."""
        base, arv = resultados[config.MODELO_PERSISTENCIA], resultados[config.MODELO_ARVORE]
        print(f"\nÁrvore × persistência na validação (N = {arv.n}):")
        print(f"  {'':<20}{'persistência':>14}{'árvore':>10}{'diferença':>11}")

        linhas = [
            (f"F1 {classe}", base.por_classe.loc[classe, "f1"], arv.por_classe.loc[classe, "f1"])
            for classe in config.CLASSES
        ]
        linhas += [
            ("F1 macro", base.f1_macro, arv.f1_macro),
            ("Balanced accuracy", base.balanced_accuracy, arv.balanced_accuracy),
        ]
        for nome, valor_base, valor_arvore in linhas:
            print(f"  {nome:<20}{valor_base:>14.4f}{valor_arvore:>10.4f}{valor_arvore - valor_base:>+11.4f}")

        # O resultado é relatado como saiu: não se troca alvo, colunas nem grade para melhorá-lo.
        diferenca = arv.f1_macro - base.f1_macro
        veredito = "ganha da" if diferenca > 0 else "perde para a" if diferenca < 0 else "empata com a"
        print(f"  A árvore {veredito} persistência em F1 macro ({diferenca:+.4f}).")

    @staticmethod
    def _imprimir_contraste(contraste: ArvoreContraste, dados: DadosModelo, resultados: dict[str, Resultado]) -> None:
        """O que a árvore de contraste fez de fato: raiz, primeiros níveis, importâncias e F1 macro lado a lado."""
        d = contraste.modelo.tree_
        print("\nÁrvore de contraste (as 8 colunas + `rtt` + região; mesmo treino, alvo e hiperparâmetros da oficial):")
        print(f"  colunas ({len(contraste.modelo.feature_names_in_)}): {', '.join(contraste.modelo.feature_names_in_)}")
        print(f"  regiões do treino (uma coluna 0/1 cada): {', '.join(dados.regioes)}")
        if dados.regioes_so_na_validacao:
            fora = ", ".join(f"{regiao} ({n} linhas)" for regiao, n in dados.regioes_so_na_validacao.items())
            print(f"  região só na validação (sem coluna: todas as colunas de região ficam 0): {fora}")
        else:
            print("  nenhuma região aparece só na validação: todas as linhas têm a coluna da própria região.")
        print(f"  max_depth {contraste.profundidade_pedida}, min_samples_leaf {contraste.folha_minima}; "
              f"profundidade obtida {d.max_depth}, folhas {d.n_leaves}")

        raiz = contraste.modelo.feature_names_in_[d.feature[0]]
        print(f"\n  A raiz divide por `{raiz}` (limiar {d.threshold[0]:.2f}).")
        print(f"  Divisões dos {config.NIVEIS_DIVISOES} primeiros níveis (N = linhas de treino que chegam ao nó):")
        for linha in contraste.divisoes_iniciais():
            print(f"    {linha}")

        # `feature_importances_` soma 1 na árvore toda; aqui só as colunas extras (as 8 oficiais ficam com o resto).
        importancias = contraste.importancias_extras()
        print("\n  Importância das colunas extras (a soma de todas as colunas da árvore é 1):")
        largura = max(len(coluna) for coluna in importancias.index)
        for coluna, valor in importancias.items():
            print(f"    {coluna:<{largura}}  {valor:.4f}")
        print(f"    {'soma das extras':<{largura}}  {importancias.sum():.4f}")

        # O que `rtt` e a região fizeram de fato, em que nível (raiz = 1) dividem pela primeira vez. "Perto da raiz" =
        # nos primeiros níveis que a saída mostra (`NIVEIS_DIVISOES`). O programa relata o que ocorreu, sem forçar.
        print(f"\n  O que as colunas extras fizeram (perto da raiz = nos {config.NIVEIS_DIVISOES} primeiros níveis):")
        rtt = config.COLUNA_RTT_CONTRASTE
        nivel_rtt = contraste.nivel_da_primeira_divisao(rtt)
        if nivel_rtt is None:
            print(f"    `{rtt}`: não divide em nenhum nível da árvore.")
        else:
            lugar = "dentro" if nivel_rtt <= config.NIVEIS_DIVISOES else "fora"
            print(f"    `{rtt}`: divide pela primeira vez no nível {nivel_rtt}, {lugar} dos {config.NIVEIS_DIVISOES} primeiros níveis.")
        niveis_regiao = {
            coluna: contraste.nivel_da_primeira_divisao(coluna) for coluna in importancias.index if coluna != rtt
        }
        dividem = {coluna: nivel for coluna, nivel in niveis_regiao.items() if nivel is not None}
        if not dividem:
            print("    regiões: nenhuma coluna de região divide em nível algum da árvore.")
        else:
            dividem_texto = ", ".join(f"{coluna} (nível {nivel})" for coluna, nivel in dividem.items())
            print(f"    regiões que dividem: {dividem_texto}.")
            sem_dividir = [coluna for coluna in niveis_regiao if coluna not in dividem]
            if sem_dividir:
                print(f"    regiões que não dividem: {', '.join(sem_dividir)}.")

        persistencia, oficial, contr = (resultados[m] for m in (config.MODELO_PERSISTENCIA, config.MODELO_ARVORE, config.MODELO_CONTRASTE))
        print(f"\n  F1 macro na validação (N = {contr.n}):")
        print(f"    persistência {persistencia.f1_macro:.4f} | árvore oficial {oficial.f1_macro:.4f} | árvore de contraste {contr.f1_macro:.4f}")
        print(f"    contraste − oficial: {contr.f1_macro - oficial.f1_macro:+.4f}")
        ExecucaoArvore._imprimir_resultado(config.MODELO_CONTRASTE, contr)
        print("\n  A árvore de contraste NÃO é o modelo do projeto e fica fora da entrega: só mostra o que a árvore faz")
        print("  quando enxerga o RTT absoluto e a região. Nada dela é gravado como modelo (só as regras em texto).")

    @staticmethod
    def _gravar_contraste(contraste: ArvoreContraste, oficial: Arvore, dados: DadosModelo, estrutura_oficial: dict) -> None:
        """Grava só o `export_text` do contraste (não é modelo: sem JSON, sem regras em português) e confere."""
        config.MODELO.mkdir(parents=True, exist_ok=True)
        texto = contraste.regras_texto()
        config.ARQUIVO_REGRAS_CONTRASTE.write_text(texto, encoding="utf-8")
        print(f"Gravado: {config.ARQUIVO_REGRAS_CONTRASTE}")

        contraste.verificar_contraste(dados, oficial, estrutura_oficial)
        # O que está no disco só cita as colunas do X do contraste e é o texto gerado, nada mais.
        no_disco = config.ARQUIVO_REGRAS_CONTRASTE.read_text(encoding="utf-8")
        Arvore.verificar_regras(no_disco, permitidas=dados.colunas_contraste())
        assert no_disco == texto, "regras_arvore_contraste.txt diferente do que foi gerado"

    @staticmethod
    def _gravar_arvore(arvore: Arvore, dados: DadosModelo, resultado: Resultado, regras: list[Regra]) -> None:
        """Grava busca, parâmetros e regras da árvore oficial, e confere o que foi para o disco."""
        config.MODELO.mkdir(parents=True, exist_ok=True)
        arvore.quadro_busca().to_csv(config.ARQUIVO_BUSCA, index=False)
        descricao = arvore.descricao()
        config.ARQUIVO_ARVORE.write_text(json.dumps(descricao, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # O arquivo é o `export_text` de sempre (a árvore inteira) e, no fim, as regras em português.
        texto = arvore.regras_texto()
        texto_portugues = Regras.texto(regras)
        config.ARQUIVO_REGRAS.write_text(texto + "\n" + texto_portugues, encoding="utf-8")
        for arquivo in (config.ARQUIVO_BUSCA, config.ARQUIVO_ARVORE, config.ARQUIVO_REGRAS):
            print(f"Gravado: {arquivo}")

        # Checagens da árvore (treino só com `treino` está em `Arvore._ajustar`; regras e semente aqui dentro).
        arvore.verificar(dados)
        # Cada regra em português seleciona exatamente as linhas que `apply` põe na folha dela.
        Regras.verificar(arvore.modelo, regras, dados)

        # A escolhida é a primeira linha da busca em memória, que está na ordem do critério: reordenar a busca
        # pelo critério não pode mudar nada. A ordem é conferida com os valores completos (em memória), não com
        # os do CSV: arredondados a `CASAS_CSV` casas, duas combinações que só diferissem depois da última casa
        # virariam empate no CSV e o desempate (que usa outras colunas) pareceria fora de ordem sem erro real.
        criterio = ["f1_macro_validacao", "max_depth", "min_samples_leaf"]
        reordenada = arvore.busca.sort_values(criterio, ascending=[False, True, False]).reset_index(drop=True)
        assert arvore.busca[criterio].equals(reordenada[criterio]), "a busca não está na ordem do critério"

        # O CSV tem de repetir essa ordem: mesmas combinações, na mesma sequência, com o F1 de validação sem
        # nunca subir de uma linha para a próxima (o empate é permitido: o arredondamento pode criá-lo).
        busca = pd.read_csv(config.ARQUIVO_BUSCA)
        combinacao = ["max_depth", "min_samples_leaf"]
        assert busca[combinacao].equals(arvore.busca[combinacao]), "busca_hiperparametros.csv fora da ordem da busca"
        assert busca["f1_macro_validacao"].is_monotonic_decreasing, "busca_hiperparametros.csv: F1 de validação sobe"
        primeira = busca.iloc[0]
        gravado = json.loads(config.ARQUIVO_ARVORE.read_text(encoding="utf-8"))
        assert gravado == descricao, "arvore_oficial.json diferente da árvore treinada"
        da_busca = (primeira["max_depth"], primeira["min_samples_leaf"])
        da_arvore = (gravado["max_depth_pedido"], gravado["min_samples_leaf_pedido"])
        assert da_busca == da_arvore, "a árvore oficial não é a primeira linha de busca_hiperparametros.csv"
        # A árvore medida na validação (fora da busca) tem o mesmo F1 macro que a linha da busca: é a mesma árvore.
        assert abs(primeira["f1_macro_validacao"] - resultado.f1_macro) <= 10**-config.CASAS_CSV, (
            "o F1 macro da árvore oficial difere do da primeira linha da busca"
        )
        # O texto gravado só cita as colunas permitidas (o que está no disco é o que o dono lê) e é o
        # `export_text` seguido das regras em português, nada mais.
        no_disco = config.ARQUIVO_REGRAS.read_text(encoding="utf-8")
        Arvore.verificar_regras(no_disco)
        assert no_disco == texto + "\n" + texto_portugues, "regras_arvore_oficial.txt diferente do que foi gerado"
