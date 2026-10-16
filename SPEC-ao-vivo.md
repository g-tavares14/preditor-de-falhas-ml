# SPEC: o modelo em tempo real (serviço ao vivo)

Spec curta, no formato do projeto. Pedido do dono em 15/10/2026: hoje o replay mostra o bloco de validação do que foi
treinado; falta rodar o mesmo modelo como se fosse uma requisição em tempo real, na API do RIPE Atlas, com **sondas
diferentes das 13 do treino**.

## Decisões do dono (15/10/2026)

1. **Forma:** o motor grava o estado e a **página do mapa ganha um modo ao vivo** (`?ao-vivo`). O comando de terminal
   também imprime o placar.
2. **Sondas:** nas 6 medições do dataset (malhas "Anchoring Mesh", intervalo de 240 s) só participam âncoras, e as 13
   âncoras do BR são exatamente as do treino. Não existe outra sonda do BR nelas. O dono escolheu **América Latina**
   (AR, BO, CL, CO, CR, EC, MX, PA, PE, PY, UY, VE, entre as que participam das 6 malhas), sorteio com a semente 16,
   10 sondas por padrão. O modelo treinou só com origem BR: sondas de outro país já são um teste de generalização.

## O que o serviço faz

Cada fluxo é `prb_id|dst_addr|msm_id`, com as mesmas 6 medições e os mesmos 6 destinos do treino.

1. **Baseline (congelado).** Busca na API as últimas `HORAS_PERIODO_A` (108 h) até o instante de partida T0, aplica o piso
   de `PISO_RTT_VALIDOS` (1.500 RTT válidos) e calcula a ficha (mediana, MAD, IQR, jitter típico). Fluxo sem 1.500 RTT
   válidos fica fora, como no treino. Nada do que chega depois de T0 entra na ficha.
2. **Ao vivo.** A cada ~60 s busca os resultados novos (6 pedidos, um por medição, com todas as sondas), calcula o X
   (as 10 colunas) com as mesmas fórmulas do Gold, e a Random Forest exportada (`modelo_final.joblib`, SHA-256 conferido
   antes de abrir) prevê a classe da 3ª medição à frente.
3. **Conferência.** Quando a 3ª medição seguinte chega (de 600 a 840 s depois), o `status_atual` dela (a regra da RFC §8.4
   com o piso da regra 3) é o futuro verdadeiro. Conta-se o acerto do modelo e o da persistência, com as mesmas métricas
   da validação (acerto e F1 macro).

O motor de cálculo é **pandas** e reimplementa as fórmulas do Spark (`gold/calculo_x/`, `gold/calculo_y/`), porque o
serviço não leva Spark nem Java. Para que a cópia não divirja, ela é conferida contra o Gold (ver Checagens).

## O que NÃO muda

`config.py` (ele faz parte do código de medição do carimbo do teste), `modelo/`, `gold/` e o teste (`TESTE_ABERTO.json`).
Os parâmetros novos ficam em `aovivo/parametros.py`. O serviço usa só o `modelo_final.joblib`; nada é retreinado e o
bloco de teste não é lido para nada além da conferência de contas (a conferência só compara as linhas de treino e de
validação do Gold).

## Saídas (todas ignoradas pelo git)

- `data/aovivo/estado.json`: sondas, T0 e fichas congeladas (o serviço retoma daqui; `--recomecar` apaga).
- `data/aovivo/medicoes.parquet`: as medições ao vivo, com a previsão congelada no instante em que a medição chegou.
- `data/aovivo/previsoes.csv` e `resumo.json`: uma linha por medição, e o placar.
- `web/dados/aovivo.json`: o mesmo formato do `replay.json` (a página reaproveita o mapa, o feed e o placar), mais
  `meta.modo = "ao_vivo"`, `meta.gerado_em` e `meta.atraso_s`.

## A página no modo ao vivo

`http://127.0.0.1:8000/?ao-vivo`. O relógio anda em tempo real, **atrasado `atraso_s` segundos** (a API do Atlas só
entrega o resultado cerca de 100 s depois da medição, mais o intervalo de consulta). A cada 30 s a página relê o JSON.
Sem barra de tempo nem velocidades. As rotas são **linhas diretas** entre a sonda e o destino (o dataset é de ping e não
tem traceroute; os cabos catalogados partem do BR e não servem para sondas de outros países). O aviso na tela diz isso.

- **Rotação do mapa:** o modo ao vivo usa `ROTACAO_AO_VIVO = [60, 0]` (`web/rotas.js`; centro em 60° O, corte em 120° L). Uma linha
  cujo círculo máximo atravessaria o corte (ex.: México → Singapura, que iria pelo Pacífico) dá a volta pelo outro lado, com um
  ponto no meio (`aovivo/pagina.py`); o `km` do cartão é o da linha desenhada, mas o **RTT mínimo teórico vem do círculo máximo**
  (o que a física permite). O serviço avisa se alguma mediana medida ficar abaixo desse mínimo.
- **Janela:** o JSON da página leva só as últimas `HORAS_NA_PAGINA` (24) horas; o CSV, o parquet e o `resumo.json` levam tudo. O
  placar da página é o dessa janela.

## Checagens (rodam em `aovivo --conferir`, e a parte offline roda em toda partida)

- **Motor × Gold (offline):** baseline, as 10 colunas do X, `regra`, `status_atual` e `status_futuro` calculados em pandas
  sobre o Silver são iguais (tolerância 1e-9) às do Gold nas linhas de treino e de validação; e a Random Forest dá a mesma
  previsão no X recalculado e no X do Gold.
- **Leitor × Silver (rede):** os resultados da API de um fluxo do treino, numa janela com timeout e perda parcial, viram
  as mesmas linhas do Silver (`t`, RTT, jitter, perda e timeout).
- **Serviço:** um fluxo sem baseline suficiente fica fora e é listado; o placar fecha com o CSV; a previsão de uma medição
  nunca muda depois de emitida.

## Limites que valem

- O rótulo é uma política (regra 3 com piso de 30 %), não a falha real do equipamento.
- Uma medição que chega atrasada (com `t` anterior ao último visto) é aceita até `SOBREPOSICAO_S` antes do último `t` visto;
  depois disso é descartada.
- O placar de um período curto tem poucas conferências: o número só diz algo com algumas centenas delas.
