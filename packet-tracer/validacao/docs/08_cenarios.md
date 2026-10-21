# Etapa 7: Cenários de teste (Período B)

**Status:** ✅ coleta concluída — 80 medições registradas no Período B, distribuídas em quatro cenários (20 medições por cenário). Classificação preliminar realizada; validação pendente.

Cenários sobre a rota BR → JP (podem ser repetidos nas outras). Em cada um: 20 rajadas, `periodo = B`, guardar `show ip route` e a tela do ping.

| # | Cenário | Como provocar no PT (ajustado às nossas portas) | Efeito esperado |
|---|---|---|---|
| 1 | Normal | Nada alterado | Métricas próximas do baseline |
| 2 | Latência elevada | No R-BR, interface **s0/3/0**: `clock rate 64000`. No Alvo-BR, gerar carga com `ping 192.168.42.10 -l 1400 -t` enquanto o Probe-BR mede BR→JP | Aumento de `latencia_relativa` e `jitter_relativo`; possível perda parcial |
| 3 | Sem resposta (ICMP bloqueado) | No R-JP: `ip access-list extended BLOQ-ICMP`, `deny icmp any any echo`, `permit ip any any`; na g0/0: `ip access-group BLOQ-ICMP out` | `rcvd = 0`, latência vazia, perda = 100, `timeout_atual = 1` |
| 4 | Queda de enlace | `shutdown` na **s0/3/0** do R-BR (ou na g0/0 do R-JP) | Timeout ou "Destination host unreachable": perda = 100 |

Na ATA, a serial do R-BR para o Japão aparece como `s0/0/0`; **no nosso PT é `s0/3/0`**.

**Checagem por caminho novo:** treinar com fluxos de um grupo (ex.: Brasil) e testar em outro (ex.: DE→PT). O fluxo novo precisa de ficha própria de baseline.


## Resultados dos cenários do Período B

Foram registradas 80 medições no Cisco Packet Tracer, distribuídas em quatro cenários da rota BR → JP.

| Cenário | Medições | OK | RISCO | FALHA |
|---|---:|---:|---:|---:|
| Normal | 20 | 16 | 4 | 0 |
| Latência elevada | 20 | 16 | 4 | 0 |
| ICMP bloqueado | 20 | 0 | 0 | 20 |
| Queda de enlace | 20 | 0 | 0 | 20 |
| **Total** | **80** | **32** | **8** | **40** |

Os dados foram processados pelo arquivo `classificar_medicoes.py`, que gerou o arquivo `data/classificacao_preliminar.csv`.

Nos cenários ICMP bloqueado e Queda de enlace, todas as medições foram classificadas como FALHA devido à perda de pacotes.

Nos cenários Normal e Latência elevada, foram identificadas medições OK e RISCO.

**Observação:** os resultados representam uma classificação preliminar baseada em regras. A validação dos critérios e a avaliação do modelo de aprendizado de máquina ainda estão pendentes.
