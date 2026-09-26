# Evolução da fonte de dados do projeto

## Ideia inicial: criar uma base própria com o RIPE Atlas

O projeto começou com a ideia de treinar um modelo usando medições reais de
ping coletadas pelo RIPE Atlas. Para observar comportamentos diferentes de
rede, o desenho escolheu quatro destinos com perfis complementares:

| Destino | Perfil esperado | Por que entrou no desenho |
|---|---|---|
| `94.140.14.14` — AdGuard DNS | Estável | Servir de referência para uma rota estável. |
| `208.67.222.222` — OpenDNS | Estável | Oferecer uma segunda referência estável. |
| `202.12.28.131` — APNIC | Rota longa | Representar um caminho de maior distância. |
| `4.2.2.1` — Level3/Lumen | Intermediário | Acrescentar um perfil intermediário de latência. |

A intenção era reunir casos variados para estudar os estados `OK`, `RISCO` e
`FALHA`. Desde esse desenho, ficou claro que a latência precisa ser interpretada
considerando a região de destino: um RTT aceitável entre continentes pode ser
ruim em uma rota local.

## Da coleta pontual para a coleta periódica

Medições pontuais serviam para testar destinos, mas não formavam o histórico
necessário para o estudo. Por isso, o plano mudou para medições periódicas, que
acumulassem observações ao longo do tempo. A primeira matriz considerava
`8.8.8.8`, `1.1.1.1` e `202.12.27.33`; a tentativa de série foi rejeitada pelo
limite de medições concorrentes do Atlas. O desenho foi então revisto para os
quatro destinos da tabela acima, com perfis estáveis, longo e intermediário.

Mesmo com a coleta periódica, a amostra disponível continuou limitada. Na
primeira tentativa de treino, a partição de teste não apresentou casos de
`FALHA`, embora existissem falhas nos dados de origem. Assim, o treino não
produziu a evidência de predição esperada. A dificuldade para ampliar a coleta
ativa por causa dos créditos reforçou que seria preciso aumentar o volume e a
variedade dos dados antes de tirar conclusões sobre a capacidade preditiva.

## Situação atual: medições públicas do RIPE Atlas no BigQuery

Para ampliar o conjunto sem depender de novas medições ativas, o projeto passou
a reutilizar medições públicas do RIPE Atlas disponíveis na tabela
`ripencc-atlas.measurements.ping` do BigQuery. A extração atual considera os
sete dias anteriores à consulta. A fonte das medições continua sendo o RIPE
Atlas; o que mudou foi o acesso ao histórico e a amplitude dos dados consultados.

O recorte atual usa 13 probes de origem e seis destinos conhecidos, organizados
em grupos regionais: `BR → BR`, `BR → América do Norte`, `BR → Europa` e
`BR → Ásia`. Os IDs das probes e os endereços dos destinos estão listados
separadamente em [`../README.md`](../README.md); isso não pressupõe que cada
probe tenha consultado cada destino.

O BigQuery fornece dados brutos para a análise. A preparação e a criação dos
rótulos continuam previstas para Python, considerando a região da rota. A
mudança busca dar ao estudo uma base mais ampla e permitir a comparação regional;
ela não significa, por si só, que a predição já esteja garantida.
