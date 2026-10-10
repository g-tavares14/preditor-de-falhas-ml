# Ficha do modelo final: preditor de degradação de rede (Random Forest)

Data: 10/10/2026. Segue a seção 5 do diário da Tarefa 5 (`projeto_preditor_redes/tarefas/Tarefa5_Arvore_Final.md`), com
os campos do diário e o que mais é preciso para reproduzir. Resultado do teste: [`resultado_teste_final.md`](resultado_teste_final.md).
Modelo exportado: `data/modelo/exportado/modelo_final.joblib`, com SHA-256 e versões no `LEIA-ME.md` da mesma pasta.

## Campos do diário

| Campo | Conteúdo |
|---|---|
| **Problema** | Classe de cada medição, **OK, RISCO ou FALHA**, pelo desvio ao baseline do próprio caminho (fluxo). O alvo é a classe da **3ª medição à frente** do mesmo fluxo, cerca de 12 minutos depois (`status_futuro`). |
| **Unidade** | Uma medição de um `fluxo_id` (sonda, destino, medição da API) no Período B. Um fluxo é `prb_id\|dst_addr\|msm_id`. |
| **Baseline** | Período A (primeiras 108 horas do dataset de 7 dias). Por fluxo: **mediana** e **MAD** do RTT válido (`rtt > 0` e sem timeout). Piso de **1.500 RTT válidos** (RFC §8.2): 79 fluxos têm baseline, 2 são `baseline_insuficiente` e ficam fora. Se o MAD é zero, a escala é `max(IQR / 1,349 ; 1 ms)` (RFC §8.4). O teste não usou medição dele mesmo para o baseline. |
| **Colunas** | As 10 colunas do X, na ordem do modelo (tabela abaixo). Nenhuma de região, país, IP, rota ou RTT absoluto. |
| **Árvore (modelo)** | Random Forest (`RandomForestClassifier`). 100 árvores, profundidade máxima 8, folha mínima 50, `max_features` sqrt, critério Gini, peso de classe {OK 1 ; RISCO 2 ; FALHA 1,5}, semente 16. Escolhida pela regra do empate (ver abaixo). |
| **Teste (uma vez)** | F1 macro **0,6699** (persistência 0,6132). Recall de FALHA **0,3816** (persistência **0,4312**). Ganho sobre a persistência **+0,0567**, IC 95 % **[+0,0168; +0,0658]**, declaração **preditor de 12 minutos** pela regra da spec. |
| **O que ela não faz** | Não classifica distância. Não opera em fluxo sem ficha (abaixo de 1.500 RTT válidos no Período A). Não antecipa bem o começo de uma falha: de OK para FALHA em 12 minutos, acerta 12,2 % no teste. Não generaliza para fluxo novo: o teste não mediu nenhum (0 fluxos fora do treino). Não mede RTT absoluto nem região. Não é medição ao vivo: classifica medições já coletadas, offline. Não diagnostica o equipamento: o alvo é a política do rótulo (piso de 30 %). |
| **Como reproduzir** | Ver a seção "Como reproduzir" abaixo: `uv sync`, depois os comandos do projeto (`arvore`, `ajuste`, `comparar`, `exportar`, `teste --ensaio`). O teste em si não se repete (a trava `TESTE_ABERTO.json` recusa). |

## Dicionário das colunas (marcado como do grupo)

> **Pendência para o dono:** o dicionário v0.4 que o diário pede ("dicionário v0.4 igual às colunas usadas") **não está
> neste repositório**. As descrições abaixo são as do grupo, escritas no código (`DESCRICAO_COLUNAS` em
> `src/preditor/modelo/exportacao.py`, com a origem em `src/preditor/gold/calculo_x/features.py`). Confira com a
> professora se o dicionário dela existe, e troque o texto se for preciso.

| # | Coluna | Significado (do grupo) | Como é calculada |
|---|---|---|---|
| 1 | `z_robusto` | Quantos desvios típicos o RTT está acima do normal do caminho. | `(rtt − mediana) / (1,4826 × MAD)`; com MAD zero, `max(IQR / 1,349 ; 1 ms)`; nulo sem RTT. |
| 2 | `aumento_pct` | Aumento percentual do RTT sobre a mediana do caminho. | `(rtt − mediana) / mediana × 100`. |
| 3 | `jitter_relativo` | Jitter da medição dividido pelo jitter típico do caminho (acima de 3 é alteração). | `jitter / jitter_tipico` do baseline; regras especiais quando o típico é zero (RFC §8.4). |
| 4 | `perda_pct` | Percentual de pings perdidos na medição. | `(enviados − recebidos) / enviados × 100`; rajada de 3 pacotes, então 0, 33, 67 ou 100. |
| 5 | `timeout_atual` | 1 se a medição inteira ficou sem resposta (sem RTT, ou perda de 100 %), 0 se não. | Indicador da própria medição (`silver/medicao.py`). |
| 6 | `n5_timeout` | Quantas das últimas 5 medições do caminho (incluindo esta) tiveram timeout. | Janela de 5 medições do mesmo fluxo, em ordem de tempo. |
| 7 | `n5_aumento80` | Quantas das últimas 5 medições tiveram aumento acima de 80 % sobre a mediana. | Mesma janela; limiar `AUMENTO_FALHA_PCT`. |
| 8 | `n5_moderado` | Quantas das últimas 5 tiveram alteração moderada (o critério de RISCO da RFC). É o `n5_risco` do diário. | Mesma janela; limiares de RISCO (`Z_RISCO`, 30 %, jitter 3). |
| 9 | `min5_z` | O menor `z_robusto` das últimas 5 medições: alto só se o desvio se manteve nas 5. | Mínimo da janela (Tarefa 4). |
| 10 | `media5_z` | A média do `z_robusto` das últimas 5 medições. | Média da janela (Tarefa 4). |

As colunas 9 e 10 são da árvore ajustada e da comparação (Tarefa 4); as demais já estavam na árvore da Tarefa 3.

## Modelo e parâmetros

Fonte: `data/modelo/comparacao/escolha.json` e os parâmetros gravados no próprio `modelo_final.joblib`.

| Parâmetro | Valor |
|---|---|
| Família | Random Forest (`RandomForestClassifier`) |
| `n_estimators` | 100 |
| `max_depth` | 8 |
| `min_samples_leaf` | 50 |
| `max_features` | sqrt (cerca de 3 das 10 colunas por divisão) |
| `criterion` | gini |
| `class_weight` | {OK: 1,0 ; RISCO: 2,0 ; FALHA: 1,5} |
| Semente | 16 |
| `fit` | só com o bloco de treino (34.661 medições) |
| Escolha | Entre as candidatas, a até 0,005 do maior F1 macro da validação, vence a mais simples. Candidatas dentro da tolerância: Random Forest (0,6977) e XGBoost (0,7006), e a árvore ajustada (0,6851) ficou fora. Pela ordem de simplicidade, a Random Forest venceu. |

Versões usadas (do `LEIA-ME.md`): Python 3.14.7, scikit-learn 1.9.1, XGBoost 3.4.1, numpy 2.5.3, pandas 3.0.6, joblib 1.6.0.

Para abrir o `.joblib`, confira o SHA-256 antes (é um pickle): `shasum -a 256 data/modelo/exportado/modelo_final.joblib`.
O valor esperado é `197579cba624b57c2d70c07e7db40524fc09d36ebfb7b9c083715e2d3809e48d`.

## Teste (uma vez)

| Número | Random Forest | Persistência |
|---|---|---|
| N | 20.507 medições, 79 fluxos | igual |
| F1 macro | **0,6699** | 0,6132 |
| Recall de FALHA | **0,3816** | 0,4312 |
| Precisão de FALHA | 0,7025 | 0,4336 |
| F1 de FALHA | 0,4946 | 0,4324 |
| Ganho sobre a persistência | +0,0567, IC 95 % [+0,0168; +0,0658] | — |
| Declaração | preditor de 12 minutos (limite inferior > 0) | — |

Validação, para comparar: F1 macro 0,6977 (Random Forest) e 0,6355 (persistência); recall de FALHA 0,5051 e 0,4983;
ganho +0,0622 [+0,0268; +0,0750]. Detalhes e a troca RISCO ↔ FALHA estão no relatório do teste.

A prova do ganho é fraca: o limite inferior do IC (+0,0168) está perto de zero. A árvore ajustada legível e o XGBoost
não foram medidos no teste.

## O que o modelo não faz (em detalhe)

- **Não classifica distância** (diário, seção 5).
- **Não opera em fluxo sem ficha:** um fluxo precisa de 1.500 RTT válidos no Período A. Os 2 insuficientes não entram.
- **Não antecipa bem o começo de uma falha:** de OK para FALHA em 12 minutos, o acerto no teste é 12,2 % (409 casos).
- **Não generaliza para fluxo novo:** todos os 79 fluxos com baseline estão no treino. O teste não responde a isso.
- **Não usa RTT absoluto, país, região, IP ou rota:** o RFC proíbe, e o X é só das 10 colunas relativas.
- **Não é medição ao vivo:** é um modelo offline sobre medições já coletadas. A página de replay reproduz a validação.
- **Não diagnostica equipamento:** o alvo é a política do rótulo (regra 3 da RFC com piso de 30 % de aumento). O modelo
  aprende essa definição de falha em medições de ping.

## Limitações do diário (seção 4)

- **Baseline fixo:** não acompanha troca de rota.
- **Rajada curta:** cada medição vem de poucos pings, e o jitter é estimado mal.
- **Anchors não são a rede de um campus:** as sondas são Anchors do RIPE Atlas.

## Como reproduzir

Dados de entrada: o dataset de 7 dias (Bronze em BigQuery; Silver e Gold em disco). O Bronze precisa de rede e de
`gcloud auth application-default login`. Os comandos abaixo usam só o que já está em disco.

```bash
uv sync                                  # instala as dependências do pacote
uv run python -m preditor gold           # data/silver/ -> data/gold/ (offline; se o Gold não existir)
uv run python -m preditor arvore         # árvore oficial da Tarefa 3 -> data/modelo/
uv run python -m preditor ajuste         # árvore ajustada da Tarefa 4 -> data/modelo/
uv run python -m preditor comparar       # Random Forest, XGBoost e persistência na validação -> data/modelo/comparacao/
uv run python -m preditor exportar       # modelo escolhido -> data/modelo/exportado/ (com LEIA-ME)
uv run python -m preditor teste --ensaio # confere os números da validação; regrava data/modelo/teste/ensaio_ok.json
shasum -a 256 data/modelo/exportado/modelo_final.joblib
```

Arquivos principais do teste:

| Arquivo | O que é |
|---|---|
| `src/preditor/modelo/execucao_teste.py` | Ensaio e abertura: trava, carimbo, medição, checagens, gravação. |
| `src/preditor/modelo/dados_teste.py` | Leitura de um bloco do Gold (o teste só com liberação explícita). |
| `src/preditor/modelo/avaliacao.py` | Métricas. O teste só se mede com `liberar_teste=True`. |
| `data/modelo/teste/` | Resultado do teste: `matriz_teste.csv`, `metricas_teste.csv`, `ic_ganho_teste.csv`, `casos_teste.txt`, `resultado.json`, `ensaio_ok.json`, `TESTE_ABERTO.json` (`concluido`). |

**O teste não se repete.** `teste --abrir-o-teste` recusa com `TESTE_ABERTO.json` presente, e apagar a trava é decisão
do dono, que deve ser registrada. Para conferir os números do teste, use os arquivos de `data/modelo/teste/`.
