"""Parâmetros do serviço ao vivo (SPEC-ao-vivo.md).

Ficam aqui e não em `config.py` porque o `config.py` faz parte do código de medição do carimbo do teste (AGENTS.md):
as constantes que já existem lá (janela, limiares, piso, 108 h, 1.500 RTT) são LIDAS de `config`, nunca copiadas.
"""

from preditor import config

# --- Onde o serviço grava ----------------------------------------------------------------------------------
PASTA = config.DADOS / "aovivo"  # `/data/*` está no .gitignore
ARQUIVO_ESTADO = PASTA / "estado.json"  # sondas, T0 e fichas do baseline (congeladas); é daqui que o serviço retoma
ARQUIVO_HISTORICO = PASTA / "historico_baseline.parquet"  # as medições cruas das 108 h do baseline (só para conferir)
ARQUIVO_MEDICOES = PASTA / "medicoes.parquet"  # as medições ao vivo, com a previsão congelada
ARQUIVO_PREVISOES = PASTA / "previsoes.csv"  # leitura humana: uma linha por medição
ARQUIVO_RESUMO = PASTA / "resumo.json"  # o placar
ARQUIVO_PAGINA = config.WEB / "dados" / "aovivo.json"  # a página no modo ao vivo (`web/dados/` é ignorada pelo git)

# --- API do RIPE Atlas ---------------------------------------------------------------------------------------
URL_API = "https://atlas.ripe.net/api/v2"  # pública, sem chave: https://atlas.ripe.net/docs/apis/rest-api-manual/
TENTATIVAS_API = 4  # em erro de rede, 429 ou 5xx; espera 2, 4, 8 s entre elas
# A janela de cada pedido de resultados do baseline. Uma janela só de 108 h devolveria dezenas de MB numa resposta e
# estoura o tempo de espera; 12 h por pedido (10 sondas × 180 medições) pesa < 1 MB.
HORAS_POR_PEDIDO = 12

# --- O laço ----------------------------------------------------------------------------------------------------
INTERVALO_CONSULTA_S = 60  # as medições chegam a cada 240 s por sonda, em instantes diferentes; 1 min pega todas cedo
# Resultados chegam atrasados (a sonda pode guardar a medição e entregar depois): cada consulta recomeça desta folga
# antes do último `t` visto. O que já existe não é duplicado (a chave é fluxo + `t`).
SOBREPOSICAO_S = 1800
# A API entrega o resultado ~100 s depois da medição (`stored_timestamp` − `timestamp`, medido em 15/10/2026: 82 a 94 s);
# somados os 60 s de consulta e a atualização da página (30 s), 300 s dão folga. É o atraso do relógio da página.
ATRASO_DA_PAGINA_S = 300
ATUALIZACAO_DA_PAGINA_S = 30  # de quanto em quanto tempo a página relê o JSON
# O JSON da página leva só as últimas horas: com 60 fluxos são ~360 medições por fluxo por dia (~3 MB por dia), e a página relê o
# arquivo a cada 30 s. O CSV, o parquet e o `resumo.json` guardam tudo; o placar da página é o dessa janela.
HORAS_NA_PAGINA = 24

# --- As sondas -------------------------------------------------------------------------------------------------
SONDAS_PADRAO = 10  # quantas sondas o sorteio traz (60 fluxos)
# América Latina (decisão do dono, 15/10/2026): as que participam das 6 malhas em 15/10/2026 foram AR, BO, CL, CO, CR,
# EC, MX, PA, PE, UY e VE (~40 sondas). Países sem sonda nas malhas simplesmente não aparecem.
PAISES_PADRAO = ("AR", "BO", "CL", "CO", "CR", "EC", "MX", "PA", "PE", "PY", "UY", "VE")

# --- As 6 medições (malhas "Anchoring Mesh Measurement", ping IPv4, 3 pacotes, intervalo de 240 s) -------------
# `msm_id` → o destino. Conferido na API em 15/10/2026: o alvo de cada uma é uma âncora, e o nome dela dá a cidade
# (de-str = Stuttgart, jp-uky = Kyoto, br-bhz = Belo Horizonte, sg-sin = Singapura, pt-lis = Lisboa, us-mia = Miami).
# `regiao` é a do Silver (`destination_region`) e a conferência abaixo exige que bata. As coordenadas são as da cidade
# (aproximadas, como as de `config.PONTOS_DESTINO`: o dataset não tem o ponto exato).
DESTINOS = {
    23589837: {"dst_addr": "129.143.66.65", "pais": "DE", "regiao": "Europa", "cidade": "Stuttgart", "ponto": [9.18, 48.78]},
    110922707: {"dst_addr": "133.69.15.4", "pais": "JP", "regiao": "Ásia", "cidade": "Kyoto", "ponto": [135.77, 35.01]},
    28095697: {"dst_addr": "150.164.1.222", "pais": "BR", "regiao": "Brasil", "cidade": "Belo Horizonte", "ponto": [-43.94, -19.92]},
    154581679: {"dst_addr": "202.6.102.41", "pais": "SG", "regiao": "Ásia", "cidade": "Singapura", "ponto": [103.82, 1.35]},
    137277732: {"dst_addr": "91.209.16.127", "pais": "PT", "regiao": "Europa", "cidade": "Lisboa", "ponto": [-9.14, 38.72]},
    23156995: {"dst_addr": "92.38.132.60", "pais": "US", "regiao": "América do Norte", "cidade": "Miami", "ponto": [-80.19, 25.76]},
}

# --- Rota na página ----------------------------------------------------------------------------------------------
# Longitude do centro do mapa no modo ao vivo: `-ROTACAO_AO_VIVO[0]` em `web/rotas.js` (60 → centro em 60° O, corte em 120° L). A linha
# direta de uma sonda a um destino que cruzaria o corte (a borda do mapa) dá a volta pelo outro lado, para não atravessar o mapa.
CENTRO_DO_MAPA_AO_VIVO = -60.0
PONTOS_PARA_CHECAR_O_CORTE = 60  # amostras do círculo máximo para ver se ele cruza o corte
AVISO_ROTA_DIRETA = "Rota ilustrativa: uma linha direta entre a sonda e o destino (sem traceroute, o caminho real não é conhecido)."
NOME_DO_TRECHO_DIRETO = "linha direta"
OPCAO_DA_ROTA_DIRETA = "Linha direta (ilustrativa)"

# --- Conferência do leitor contra o Silver ---------------------------------------------------------------------
TOLERANCIA = 1e-9  # Motor × Gold: o Spark e o pandas somam em ordens diferentes
# Leitor × Silver: o RTT de cada ping chega ao Silver como float32 (o BigQuery guarda assim; ex.: um jitter de 0,19818115234375
# no Silver contra 0,19818550000000812 da API) e o da API é double. O float32 erra ~6e-8 em termos relativos (~1e-5 ms num RTT de
# 200 ms), e o jitter, que é uma diferença de RTTs, herda esse erro absoluto. Por isso a conferência do leitor usa 1e-6 relativo
# e 1e-4 ms absolutos (10x o erro do float32), muito abaixo do que muda uma classe (jitter relativo >= 3, z >= 2).
TOLERANCIA_LEITOR_REL = 1e-6
TOLERANCIA_LEITOR_ABS_MS = 1e-4
FOLGA_DA_JANELA_S = 3600  # a janela da API em volta da medição escolhida na conferência do leitor
