"""Leitura do dataset rotulado e preparo de X e y para a árvore (SPEC-arvore.md, "Alvo").

Entrada: `dataset_rotulado_B.parquet` do Gold, como está. Nada do X nem do Y é recalculado aqui.
"""

import numpy as np
import pandas as pd

from preditor import config

# Blocos que o modelo usa de verdade. O teste só é contado (N): fica fechado até a Tarefa 5.
BLOCOS_USADOS = (config.BLOCO_TREINO, config.BLOCO_VALIDACAO)


class DadosModelo:
    def __init__(self) -> None:
        self.X: dict[str, pd.DataFrame] = {}  # bloco → as 8 colunas da árvore, em float64
        self.y: dict[str, pd.Series] = {}  # bloco → `status_futuro`
        # `status_atual` das linhas mantidas da validação, alinhado ao `y` pelo índice. Só serve à persistência
        # ("o futuro é igual ao agora"): é proibido no X (vazaria a resposta), então vem por este caminho à parte.
        self.status_atual_validacao = pd.Series(dtype="object")
        # Onde está cada linha mantida da validação (`fluxo_id`, `t`, `rtt`) e a mediana do baseline do fluxo dela,
        # alinhados ao `y` pelo índice. Só localizam e classificam os erros concretos: todas são proibidas no X.
        self.localizacao_validacao = pd.DataFrame()
        # Mediana do baseline de cada fluxo que entra no modelo (índice = `fluxo_id`) e a mediana dessas medianas.
        self.mediana_por_fluxo = pd.Series(dtype="float64")
        self.mediana_das_medianas = float("nan")
        # Colunas EXTRAS da árvore de contraste (`rtt` e uma coluna 0/1 por região), alinhadas ao X pelo índice, só de
        # treino e validação. Ficam fora do X oficial, que continua com as 8 colunas: só `x_contraste` os junta.
        self.extras_contraste: dict[str, pd.DataFrame] = {}
        self.regioes: list[str] = []  # as categorias de região: as do TREINO (a validação é codificada com elas)
        self.regioes_so_na_validacao: dict[str, int] = {}  # região que o treino não viu → linhas da validação (colunas 0)
        self.resumo: dict[str, dict[str, int]] = {}  # bloco → quantas linhas saíram e por quê
        self.n_teste = 0  # o único número do teste que o programa guarda

    def carregar(self) -> "DadosModelo":
        """Lê o Gold, aplica a folga, descarta o futuro nulo e separa X e y por bloco."""
        lido = self._ler()
        self._separar(self._marcar_folga(lido))
        self._juntar_medianas()
        # A verificação parte do dataset como foi lido, sem a marca nem a ordenação da folga.
        self._verificar(lido)
        return self

    def colunas_contraste(self) -> list[str]:
        """As colunas do X da árvore de contraste: as 8 oficiais, `rtt` e uma coluna 0/1 por região do treino."""
        return (
            config.COLUNAS_ARVORE
            + [config.COLUNA_RTT_CONTRASTE]
            + [config.PREFIXO_REGIAO + regiao for regiao in self.regioes]
        )

    def x_contraste(self, bloco: str) -> pd.DataFrame:
        """X do contraste de um bloco: o X oficial mais as colunas extras (um caminho à parte; o X oficial não muda)."""
        return pd.concat([self.X[bloco], self.extras_contraste[bloco]], axis=1)

    @staticmethod
    def _ler() -> pd.DataFrame:
        if not config.ARQUIVO_ROTULADO.exists():
            # Mesmo formato de `Pipeline._ler_camada`: mensagem em stderr, código 1, sem traceback.
            raise SystemExit(
                f"Não encontrei {config.ARQUIVO_ROTULADO}.\n"
                "Rode antes: uv run python -m preditor gold"
            )
        return pd.read_parquet(config.ARQUIVO_ROTULADO)

    @staticmethod
    def _marcar_folga(rotulado: pd.DataFrame) -> pd.DataFrame:
        """Marca as 3 últimas medições de cada (fluxo, bloco) de treino e validação (RFC §9)."""
        # O futuro dessas medições (3 passos à frente) cai no bloco seguinte: se ficassem, a árvore
        # aprenderia (treino) ou seria medida (validação) com resposta de outro bloco.
        # A marca vem ANTES de descartar o `status_futuro` nulo: depois do descarte, as "3 últimas"
        # seriam outras linhas e o futuro do bloco seguinte entraria sem ser notado.
        # Ordenar por `t` (estável) dá a ordem de tempo; `fluxo_id` e `t` nunca se repetem juntos (Silver).
        ordenado = rotulado.sort_values("t", kind="stable")
        # cumcount(ascending=False): 0 = última medição do fluxo no bloco, 1 = penúltima, 2 = antepenúltima.
        posicao_do_fim = ordenado.groupby(["fluxo_id", "bloco"]).cumcount(ascending=False)
        # No teste não há folga a aplicar: o futuro das últimas é nulo por fim de série, não por bloco vizinho.
        ordenado["folga"] = (posicao_do_fim < config.PASSOS_FUTURO) & (ordenado["bloco"] != config.BLOCO_TESTE)
        return ordenado

    def _separar(self, rotulado: pd.DataFrame) -> None:
        tem_futuro = rotulado[config.ALVO].notna()
        mantida = tem_futuro & ~rotulado["folga"]  # com futuro e fora da folga: a linha entra no modelo

        # As categorias de região do contraste vêm só do treino mantido: a validação nunca decide quais colunas existem.
        treino_mantido = rotulado[(rotulado["bloco"] == config.BLOCO_TREINO) & mantida]
        self.regioes = sorted(treino_mantido[config.COLUNA_REGIAO_CONTRASTE].dropna().unique())

        for bloco in BLOCOS_USADOS:
            no_bloco = rotulado["bloco"] == bloco
            # Futuro nulo: a 3ª medição seguinte não existe ou não está de 10 a 14 min depois (RFC §3).
            # Folga: só conta aqui as que tinham futuro; as que já eram nulas saíram pelo motivo anterior.
            nulo = int((no_bloco & ~tem_futuro).sum())
            folga = int((no_bloco & tem_futuro & rotulado["folga"]).sum())
            mantidas = rotulado[no_bloco & mantida]

            # Valores ausentes ficam ausentes (RFC §8.3): só `astype`, nenhum `fillna`.
            self.X[bloco] = mantidas[config.COLUNAS_ARVORE].astype("float64")
            self.y[bloco] = mantidas[config.ALVO]
            self.extras_contraste[bloco] = self._extras_contraste(mantidas)
            if bloco == config.BLOCO_VALIDACAO:
                self.regioes_so_na_validacao = self._regioes_sem_coluna(mantidas)
                self.status_atual_validacao = mantidas["status_atual"]
                # Só da validação: o teste não guarda coluna nenhuma.
                self.localizacao_validacao = mantidas[config.COLUNAS_LOCALIZACAO].copy()
            self.resumo[bloco] = {
                "linhas": int(no_bloco.sum()),
                "futuro_nulo": nulo,
                "folga": folga,
                "n": len(mantidas),
            }

        # Teste: só o N. Nenhuma coluna dele é guardada.
        self.n_teste = int(((rotulado["bloco"] == config.BLOCO_TESTE) & tem_futuro).sum())

    def _extras_contraste(self, mantidas: pd.DataFrame) -> pd.DataFrame:
        """`rtt` (ms) e a região em colunas 0/1, para a árvore de contraste (diário da Tarefa 3, seção 4)."""
        # `rtt` ausente continua ausente (RFC §8.3): só `astype`, nenhum `fillna`.
        rtt = mantidas[config.COLUNA_RTT_CONTRASTE].astype("float64")
        extras = pd.DataFrame({config.COLUNA_RTT_CONTRASTE: rtt}, index=mantidas.index)
        for nome in self.regioes:
            extras[config.PREFIXO_REGIAO + nome] = (mantidas[config.COLUNA_REGIAO_CONTRASTE] == nome).astype("float64")
        return extras

    def _regioes_sem_coluna(self, mantidas: pd.DataFrame) -> dict[str, int]:
        """Região cujas linhas ficam com todas as colunas de região em 0 (o treino não a viu) → quantas linhas."""
        regiao = mantidas[config.COLUNA_REGIAO_CONTRASTE]
        sem_coluna = regiao[~regiao.isin(self.regioes)].value_counts(dropna=False)
        return {"(ausente)" if pd.isna(nome) else str(nome): int(n) for nome, n in sem_coluna.items()}

    def _juntar_medianas(self) -> None:
        """Lê a mediana do baseline de cada fluxo e a põe em cada linha da validação (só para os erros concretos)."""
        if not config.ARQUIVO_BASELINE.exists():
            raise SystemExit(
                f"Não encontrei {config.ARQUIVO_BASELINE}.\n"
                "Rode antes: uv run python -m preditor gold"
            )
        baseline = pd.read_parquet(config.ARQUIVO_BASELINE)

        # "Mediana das medianas" = mediana, entre os fluxos com baseline suficiente, da `mediana` de cada um.
        # São os fluxos que entram no modelo (os 2 `baseline_insuficiente` não têm mediana e não têm linha no
        # dataset rotulado; o 82º fluxo do Silver, só do Período B, nem está no baseline). Cada fluxo pesa
        # igual, não importa quantas medições ele tem. Quem está EXATAMENTE na mediana (com 79 fluxos, um) não
        # é nem longo nem curto: fica fora dos dois casos.
        com_baseline = baseline.loc[~baseline["baseline_insuficiente"]]
        self.mediana_por_fluxo = com_baseline.set_index("fluxo_id")["mediana"]
        self.mediana_das_medianas = float(self.mediana_por_fluxo.median())

        # `map` por `fluxo_id` mantém o índice da validação (o mesmo do `y`): a mediana é só um rótulo da linha.
        medianas = self.localizacao_validacao["fluxo_id"].map(self.mediana_por_fluxo)
        self.localizacao_validacao[config.COLUNA_MEDIANA_FLUXO] = medianas

    def _verificar(self, lido: pd.DataFrame) -> None:
        assert set(lido["bloco"]) == {config.BLOCO_TREINO, config.BLOCO_VALIDACAO, config.BLOCO_TESTE}, (
            f"blocos inesperados no dataset: {sorted(set(lido['bloco']))}"
        )
        # Coluna nova no Gold: obriga a decidir se é feature (`COLUNAS_ARVORE`) ou proibida.
        # Sem isso, ela ficaria fora das duas listas sem ninguém notar.
        sem_decisao = set(lido.columns) - set(config.COLUNAS_ARVORE) - set(config.COLUNAS_PROIBIDAS)
        assert not sem_decisao, f"colunas do Gold fora de COLUNAS_ARVORE e COLUNAS_PROIBIDAS: {sorted(sem_decisao)}"
        # Só treino e validação têm X e y: o teste não é guardado.
        assert set(self.X) == set(BLOCOS_USADOS) == set(self.y), f"blocos com dados: {sorted(self.X)}"

        # Folga conferida pelo tempo, sem usar a marca de `_marcar_folga` nem a ordenação dela: reordena
        # por (fluxo, tempo) e olha em que bloco está a 3ª medição seguinte do mesmo fluxo.
        # Se for outro bloco, o futuro vem de fora e a linha não pode estar em treino nem validação.
        por_fluxo = lido.sort_values(["fluxo_id", "t"])
        bloco_do_futuro = por_fluxo.groupby("fluxo_id")["bloco"].shift(-config.PASSOS_FUTURO)

        for bloco in BLOCOS_USADOS:
            X, y = self.X[bloco], self.y[bloco]
            resumo = self.resumo[bloco]

            assert list(X.columns) == config.COLUNAS_ARVORE, f"{bloco}: X com colunas diferentes das 8: {list(X.columns)}"
            proibidas = set(X.columns) & set(config.COLUNAS_PROIBIDAS)
            assert not proibidas, f"{bloco}: colunas proibidas no X: {sorted(proibidas)}"
            assert (X.dtypes == "float64").all(), f"{bloco}: X precisa ser float64 (com NaN): {dict(X.dtypes)}"
            assert X.index.equals(y.index), f"{bloco}: X e y com linhas diferentes"

            assert y.notna().all(), f"{bloco}: sobrou status_futuro nulo"
            assert set(y) <= set(config.CLASSES), f"{bloco}: classe fora de {config.CLASSES}: {sorted(set(y))}"
            # Treino e validação precisam das 3 classes (o recorte garante; a árvore depende disso).
            assert set(y) == set(config.CLASSES), f"{bloco}: falta classe: {sorted(set(y))}"

            # Folga: toda linha mantida tem o futuro (3ª medição seguinte) no próprio bloco. Como o
            # `status_futuro` não é nulo, a 3ª seguinte existe; se não estivesse no bloco, seria `!=`.
            futuro_fora = X.index[bloco_do_futuro.loc[X.index] != bloco]
            assert futuro_fora.empty, f"{bloco}: {len(futuro_fora)} linhas mantidas têm o futuro em outro bloco (folga)"

            # Nada foi preenchido: os NaN do X são os mesmos NaN do dataset, coluna a coluna.
            nulos_origem = lido.loc[X.index, config.COLUNAS_ARVORE].isna().sum()
            assert (X.isna().sum() == nulos_origem).all(), f"{bloco}: valores ausentes foram alterados"

            # As contas fecham: linhas do bloco − futuro nulo − folga = N.
            assert resumo["linhas"] - resumo["futuro_nulo"] - resumo["folga"] == resumo["n"] == len(X), (
                f"{bloco}: as linhas removidas não fecham com o N: {resumo}"
            )

        # `status_atual` da validação (só a persistência o usa): as mesmas linhas do y, com o valor que o
        # dataset lido tem (sem nulos). Fica fora do laço porque só a validação o guarda.
        bloco = config.BLOCO_VALIDACAO
        atual = self.status_atual_validacao
        assert atual.index.equals(self.y[bloco].index), f"{bloco}: status_atual e y com linhas diferentes"
        assert atual.equals(lido.loc[atual.index, "status_atual"]), f"{bloco}: status_atual alterado"
        assert set(atual) <= set(config.CLASSES), f"{bloco}: status_atual fora de {config.CLASSES}"

        self._verificar_contraste(lido)

        # Localização da validação: um caminho separado do X, sem enfraquecer as checagens do X acima.
        # São as mesmas linhas do y, com os valores do dataset lido, e nenhuma delas é coluna do X.
        loc = self.localizacao_validacao
        assert list(loc.columns) == config.COLUNAS_LOCALIZACAO + [config.COLUNA_MEDIANA_FLUXO], (
            f"{bloco}: colunas de localização inesperadas: {list(loc.columns)}"
        )
        assert loc.index.equals(self.y[bloco].index), f"{bloco}: localização e y com linhas diferentes"
        assert not set(loc.columns) & set(self.X[bloco].columns), f"{bloco}: coluna de localização dentro do X"
        assert loc[config.COLUNAS_LOCALIZACAO].equals(lido.loc[loc.index, config.COLUNAS_LOCALIZACAO]), (
            f"{bloco}: fluxo_id, t ou rtt alterados"
        )
        # Os fluxos com baseline suficiente são exatamente os do dataset: nenhuma linha fica sem mediana,
        # e nenhum fluxo com mediana fica de fora da "mediana das medianas".
        assert set(self.mediana_por_fluxo.index) == set(lido["fluxo_id"]), (
            "os fluxos com baseline suficiente não são os fluxos do dataset rotulado"
        )
        assert self.mediana_por_fluxo.notna().all(), "fluxo com baseline suficiente e sem mediana"
        assert loc[config.COLUNA_MEDIANA_FLUXO].notna().all(), f"{bloco}: linha da validação sem mediana de baseline"
        # Conferência por outro caminho (numpy puro, sem o `median` do pandas).
        assert np.isclose(self.mediana_das_medianas, np.median(self.mediana_por_fluxo.to_numpy()), rtol=0, atol=config.TOLERANCIA_METRICA), (
            "a mediana das medianas não bate"
        )

    def _verificar_contraste(self, lido: pd.DataFrame) -> None:
        """Confere as colunas extras do contraste contra o dataset lido, sem alterar nenhuma checagem do X oficial."""
        assert set(self.extras_contraste) == set(BLOCOS_USADOS), f"blocos do contraste: {sorted(self.extras_contraste)}"
        # As colunas de contraste são do dataset e proibidas no X oficial: só esta árvore as vê.
        assert set(config.COLUNAS_CONTRASTE) <= set(lido.columns) & set(config.COLUNAS_PROIBIDAS), (
            f"colunas de contraste fora do dataset ou da lista de proibidas: {config.COLUNAS_CONTRASTE}"
        )
        # As categorias são as do treino mantido, achadas de novo a partir do dataset lido.
        treino = lido.loc[self.X[config.BLOCO_TREINO].index, config.COLUNA_REGIAO_CONTRASTE]
        assert self.regioes == sorted(treino.dropna().unique()), "as regiões do contraste não são as do treino"
        assert self.regioes, "o treino não tem região nenhuma"

        for bloco in BLOCOS_USADOS:
            extras, X = self.extras_contraste[bloco], self.X[bloco]
            esperadas = [config.COLUNA_RTT_CONTRASTE] + [config.PREFIXO_REGIAO + regiao for regiao in self.regioes]
            assert list(extras.columns) == esperadas, f"{bloco}: colunas extras do contraste: {list(extras.columns)}"
            assert extras.index.equals(X.index), f"{bloco}: extras do contraste e X com linhas diferentes"
            assert (extras.dtypes == "float64").all(), f"{bloco}: extras do contraste precisam ser float64"
            assert not set(extras.columns) & set(X.columns), f"{bloco}: coluna extra repetida no X oficial"
            assert list(self.x_contraste(bloco).columns) == self.colunas_contraste(), f"{bloco}: X do contraste fora do esperado"

            origem = lido.loc[X.index]
            # `rtt` é o do dataset, com os mesmos ausentes (`equals` trata NaN como igual a NaN).
            rtt = config.COLUNA_RTT_CONTRASTE
            assert extras[rtt].equals(origem[rtt].astype("float64")), f"{bloco}: `{rtt}` do contraste foi alterado"
            for regiao in self.regioes:
                coluna = extras[config.PREFIXO_REGIAO + regiao].to_numpy()
                assert (coluna == (origem[config.COLUNA_REGIAO_CONTRASTE] == regiao).to_numpy()).all(), (
                    f"{bloco}: coluna 0/1 da região {regiao} não bate com o dataset"
                )
            # Cada linha tem no máximo uma região em 1; todas em 0 só quando a região não é uma das do treino.
            soma = extras.drop(columns=config.COLUNA_RTT_CONTRASTE).sum(axis=1)
            assert (soma <= 1).all(), f"{bloco}: linha com mais de uma região"
            todas_zero = int((soma == 0).sum())
            assert todas_zero == int((~origem[config.COLUNA_REGIAO_CONTRASTE].isin(self.regioes)).sum()), (
                f"{bloco}: linhas com todas as regiões em 0 não são as de região fora do treino"
            )
            if bloco == config.BLOCO_VALIDACAO:
                assert todas_zero == sum(self.regioes_so_na_validacao.values()), "contagem das regiões só da validação"
