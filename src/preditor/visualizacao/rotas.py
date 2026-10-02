"""Monta a rota simulada de cada fluxo, em trechos terrestres e submarinos (SPEC-visualizacao.md, "Rota simulada").

O dataset é de ping e não tem traceroute: a rota é ilustrativa. Os cabos e os pontos de troca de tráfego existem
(catálogo em `config.py`), mas o caminho de cada fluxo por eles é escolha nossa, a mesma em toda execução.
Tudo em [longitude, latitude], com a longitude em [-180, 180].
"""

import hashlib
import json
import math

import pandas as pd

from preditor import config


class Geografia:
    @staticmethod
    def distancia_km(a: list[float], b: list[float]) -> float:
        """Distância em círculo máximo entre dois pontos [lon, lat] (fórmula de haversine)."""
        lon_a, lat_a = math.radians(a[0]), math.radians(a[1])
        lon_b, lat_b = math.radians(b[0]), math.radians(b[1])
        # O haversine usa só a diferença de longitude dentro de um seno: 170° e -170° dão 20°, sem "desdobrar" nada.
        parte = (
            math.sin((lat_b - lat_a) / 2) ** 2
            + math.cos(lat_a) * math.cos(lat_b) * math.sin((lon_b - lon_a) / 2) ** 2
        )
        return 2 * config.RAIO_TERRA_KM * math.asin(math.sqrt(parte))

    @staticmethod
    def comprimento_km(caminho: list[list[float]]) -> float:
        """Soma das distâncias entre pontos consecutivos do caminho."""
        return sum(Geografia.distancia_km(a, b) for a, b in zip(caminho, caminho[1:]))

    @staticmethod
    def rtt_minimo_ms(km: float) -> float:
        """RTT mínimo teórico na fibra: ida e volta, a ~200 km por ms (`config.VELOCIDADE_FIBRA_KM_POR_MS`)."""
        return 2 * km / config.VELOCIDADE_FIBRA_KM_POR_MS


class Sondas:
    @staticmethod
    def ler() -> dict[int, list[float]]:
        """`prb_id` → [lon, lat], lido do CSV versionado. Sem o arquivo, pede o script que o gera (a coleta precisa de rede)."""
        if not config.ARQUIVO_SONDAS.exists():
            raise SystemExit(
                f"Não encontrei {config.ARQUIVO_SONDAS}.\nRode antes: uv run python -m preditor.visualizacao.coletar_sondas"
            )
        tabela = pd.read_csv(config.ARQUIVO_SONDAS)
        assert tabela["prb_id"].is_unique, f"prb_id repetido em {config.ARQUIVO_SONDAS.name}"
        assert tabela[["longitude", "latitude"]].notna().all().all(), f"sonda sem coordenada em {config.ARQUIVO_SONDAS.name}"
        assert tabela["longitude"].between(-180, 180).all() and tabela["latitude"].between(-90, 90).all(), (
            f"coordenada inválida em {config.ARQUIVO_SONDAS.name}"
        )
        return {int(linha.prb_id): [float(linha.longitude), float(linha.latitude)] for linha in tabela.itertuples()}

    @staticmethod
    def do_gold() -> list[int]:
        """Os `prb_id` de todos os fluxos do baseline, sem repetição e em ordem crescente."""
        if not config.ARQUIVO_BASELINE.exists():
            raise SystemExit(f"Não encontrei {config.ARQUIVO_BASELINE}.\nRode antes: uv run python -m preditor gold")
        fluxos = pd.read_parquet(config.ARQUIVO_BASELINE, columns=["fluxo_id"])["fluxo_id"]
        # `fluxo_id` = `prb_id|dst_addr|msm_id` (AGENTS.md): a sonda é o primeiro pedaço.
        return sorted({int(fluxo.split("|")[0]) for fluxo in fluxos})


class Rotas:
    def __init__(self) -> None:
        self.sondas = Sondas.ler()

    def montar(self, fluxo_id: str, pais: str, mediana: float) -> dict:
        """A rota do fluxo: opção escolhida, km, RTT mínimo teórico e a lista de trechos.

        `mediana` = mediana real do RTT do fluxo no baseline (ms); `NaN` se o fluxo não tem (`baseline_insuficiente`).
        """
        possiveis = self.rotas_possiveis(fluxo_id, pais, mediana)
        # O sorteio é só entre as possíveis: a semente + o `fluxo_id` dão sempre o mesmo índice (determinístico).
        return possiveis[self._indice_da_rota(fluxo_id, len(possiveis))]

    def rotas_possiveis(self, fluxo_id: str, pais: str, mediana: float) -> list[dict]:
        """As rotas candidatas do fluxo que cabem na mediana real: RTT mínimo teórico <= mediana (a luz não chega antes)."""
        candidatas = self._candidatas(fluxo_id, pais)
        if pd.isna(mediana):
            # Sem mediana não há como filtrar: valem todas.
            return candidatas
        possiveis = [rota for rota in candidatas if rota["rtt_minimo_ms"] <= mediana]
        if possiveis:
            return possiveis
        # Nenhuma cabe (o RTT medido é menor que qualquer rota nossa): fica a de menor RTT mínimo, a menos impossível.
        return [min(candidatas, key=lambda rota: rota["rtt_minimo_ms"])]

    def _candidatas(self, fluxo_id: str, pais: str) -> list[dict]:
        """Toda combinação (opção de rota × ponto candidato do destino), sem repetir rotas idênticas."""
        # `fluxo_id` = `prb_id|dst_addr|msm_id` (AGENTS.md).
        prb_id, dst_addr, _ = fluxo_id.split("|")
        assert int(prb_id) in self.sondas, f"sonda {prb_id} sem coordenada em {config.ARQUIVO_SONDAS.name}"
        assert pais in config.ROTAS_POR_PAIS, f"país {pais!r} sem rotas em config.ROTAS_POR_PAIS"
        assert pais in config.PONTOS_DESTINO, f"país {pais!r} sem ponto em config.PONTOS_DESTINO"

        sonda = self._no("sonda", f"sonda {prb_id}", self.sondas[int(prb_id)])
        pontos = config.PONTOS_DESTINO[pais]
        cidades = [cidade for cidade, _ in pontos]

        candidatas = []
        ja_vistas = set()
        for opcao in config.ROTAS_POR_PAIS[pais]:
            # `destinos` ausente = a opção vale para todos os pontos do país.
            destinos = opcao.get("destinos", cidades)
            assert set(destinos) <= set(cidades), f"opção {opcao['nome']!r}: destinos {destinos} fora de {cidades}"
            for cidade, ponto in pontos:
                if cidade not in destinos:
                    continue
                destino = self._no_destino(cidade, ponto, dst_addr)
                rota = self._montar_rota(opcao, sonda, destino)
                # Opções diferentes podem dar a MESMA rota para esta sonda (ex.: duas entradas no Monet para uma sonda
                # de Fortaleza). Só a primeira fica, para a escolha não pesar mais para o que se repete.
                assinatura = json.dumps(rota["trechos"])
                if assinatura not in ja_vistas:
                    ja_vistas.add(assinatura)
                    candidatas.append(rota)
        assert candidatas, f"{pais}: nenhuma combinação de rota e destino"
        return candidatas

    def _montar_rota(self, opcao: dict, sonda: dict, destino: dict) -> dict:
        """Uma opção de rota para uma sonda e um destino: trechos encadeados, km e RTT mínimo teórico."""
        trechos = []
        no_atual = sonda
        for etapa in opcao["etapas"]:
            if "terrestre" in etapa:
                trecho = self._trecho_terrestre(etapa, no_atual, destino, primeiro=not trechos)
            else:
                trecho = self._trecho_submarino(etapa, no_atual)
            trechos.append(trecho)
            # A próxima etapa começa onde esta terminou (trechos encadeados).
            no_atual = trecho["nos"][-1]

        # km da rota = soma dos km (já arredondados) dos trechos: o que a página soma é o que o arquivo diz.
        km = round(sum(trecho["km"] for trecho in trechos), config.CASAS_KM)
        return {
            "opcao": opcao["nome"],
            "km": km,
            "rtt_minimo_ms": round(Geografia.rtt_minimo_ms(km), config.CASAS_RTT_REPLAY),
            "trechos": trechos,
        }

    @staticmethod
    def _indice_da_rota(fluxo_id: str, quantas: int) -> int:
        """Escolhe uma das rotas com a semente do projeto + o `fluxo_id`: o mesmo fluxo sempre cai na mesma rota."""
        # SHA-256 é estável entre execuções; o `hash()` do Python não é (ele muda a cada processo).
        resumo = hashlib.sha256(f"{config.SEMENTE}|{fluxo_id}".encode("utf-8")).digest()
        return int.from_bytes(resumo[:8], "big") % quantas

    @staticmethod
    def _no(tipo: str, nome: str, ponto: list[float]) -> dict:
        arredondado = [round(coordenada, config.CASAS_COORDENADA) for coordenada in ponto]
        return {"tipo": tipo, "nome": nome, "ponto": arredondado}

    @staticmethod
    def _no_destino(cidade: str, ponto: list[float], dst_addr: str) -> dict:
        """O ponto candidato com um pequeno deslocamento que depende só do `dst_addr` (spec, "Coordenadas")."""
        longitude, latitude = ponto
        resumo = hashlib.sha256(f"{config.SEMENTE}|{dst_addr}".encode("utf-8")).digest()
        # Dois números de 4 bytes viram dois deslocamentos entre -1 e 1; multiplicados pelo máximo, ficam em ±0,2°.
        desloc_lon = int.from_bytes(resumo[0:4], "big") / 0xFFFFFFFF * 2 - 1
        desloc_lat = int.from_bytes(resumo[4:8], "big") / 0xFFFFFFFF * 2 - 1
        deslocado = [
            longitude + desloc_lon * config.DESLOCAMENTO_DESTINO_GRAUS,
            latitude + desloc_lat * config.DESLOCAMENTO_DESTINO_GRAUS,
        ]
        return Rotas._no("destino", f"{cidade} ({dst_addr})", deslocado)

    @staticmethod
    def _trecho(tipo: str, nome: str, nos: list[dict], caminho: list[list[float]]) -> dict:
        return {
            "tipo": tipo,
            "nome": nome,
            "km": round(Geografia.comprimento_km(caminho), config.CASAS_KM),
            "nos": nos,
            "caminho": caminho,
        }

    def _trecho_terrestre(self, etapa: dict, no_atual: dict, destino: dict, primeiro: bool) -> dict:
        """Backbone por terra: do nó atual, pelos pops, até uma estação de aterragem ou o destino."""
        nomes_dos_pops = list(etapa["via"])
        if primeiro:
            # A sonda sai pelo IX.br mais perto dela (e, no Sul, passa por Curitiba); se a etapa já passa por um
            # desses pontos, não o repete.
            ix_local = self._ix_mais_perto(no_atual["ponto"])
            saida = [ix_local]
            if ix_local in config.PASSAGEM_APOS_IX_LOCAL:
                saida.append(config.PASSAGEM_APOS_IX_LOCAL[ix_local])
            nomes_dos_pops = saida + [nome for nome in nomes_dos_pops if nome not in saida]

        nos = [no_atual]
        for nome in nomes_dos_pops:
            assert nome in config.HUBS, f"pop {nome!r} sem coordenada em config.HUBS"
            nos.append(self._no("pop", nome, config.HUBS[nome]))

        chegada = etapa["ate"]
        if chegada == "destino":
            nos.append(destino)
        else:
            if isinstance(chegada, list):
                # Lista de estações: fica a mais perto de onde a rota está agora.
                chegada = min(chegada, key=lambda nome: Geografia.distancia_km(nos[-1]["ponto"], config.ATERRAGENS[nome]))
            nos.append(self._no_aterragem(chegada))
        # Por terra a linha vai direto de um nó ao seguinte: o caminho são os próprios pontos dos nós.
        return self._trecho("terrestre", etapa["terrestre"], nos, [no["ponto"] for no in nos])

    @staticmethod
    def _ix_mais_perto(ponto: list[float]) -> str:
        return min(config.IXS_BRASIL, key=lambda nome: Geografia.distancia_km(ponto, config.HUBS[nome]))

    @staticmethod
    def _no_aterragem(nome: str) -> dict:
        assert nome in config.ATERRAGENS, f"estação {nome!r} sem coordenada em config.ATERRAGENS"
        return Rotas._no("aterragem", nome, config.ATERRAGENS[nome])

    def _trecho_submarino(self, etapa: dict, no_atual: dict) -> dict:
        """Um cabo do catálogo, da estação onde a rota está até a estação `ate` (em qualquer sentido do cabo)."""
        nome_do_cabo = etapa["cabo"]
        assert nome_do_cabo in config.CABOS, f"cabo {nome_do_cabo!r} fora do catálogo config.CABOS"
        assert no_atual["tipo"] == "aterragem", f"o cabo {nome_do_cabo} precisa começar numa estação, não em {no_atual['tipo']}"
        pontos = config.CABOS[nome_do_cabo]["pontos"]

        inicio = self._posicao_da_estacao(pontos, no_atual["nome"], nome_do_cabo)
        fim = self._posicao_da_estacao(pontos, etapa["ate"], nome_do_cabo)
        assert inicio != fim, f"o cabo {nome_do_cabo} começa e termina em {etapa['ate']}"
        # O cabo é lido no sentido do traçado; para ir no sentido contrário, inverte-se o pedaço escolhido.
        pedaco = pontos[inicio : fim + 1] if inicio < fim else pontos[fim : inicio + 1][::-1]

        nos = []
        caminho = []
        for ponto in pedaco:
            if isinstance(ponto, str):
                # Texto = estação de aterragem (nó nomeado). As do meio, como Fortaleza no Monet, também viram nó.
                no = self._no_aterragem(ponto)
                nos.append(no)
                caminho.append(no["ponto"])
            else:
                # Lista = ponto no mar: só dá forma à linha, não é nó.
                caminho.append([round(coordenada, config.CASAS_COORDENADA) for coordenada in ponto])
        return self._trecho("submarino", nome_do_cabo, nos, caminho)

    @staticmethod
    def _posicao_da_estacao(pontos: list, estacao: str, cabo: str) -> int:
        assert estacao in pontos, f"{estacao!r} não é estação do cabo {cabo}"
        return pontos.index(estacao)
