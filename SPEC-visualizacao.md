# Spec: Visualização (replay no mapa-múndi)

Status: **aprovada pelo dono em 01/10/2026**, com as decisões da seção "Decisões do dono".

## Objetivo

Mostrar o preditor funcionando, em uma página web: um mapa-múndi em que cada medição de ping aparece como um pulso
que sai da sonda no Brasil, percorre uma rota até o destino e volta, enquanto a árvore prevê a classe do fluxo 12
minutos à frente. Quando o relógio chega nesse futuro, a página mostra se a previsão acertou.

É um **replay**: a página reproduz, em tempo acelerado, medições que já estão no Gold. Nada é medido ao vivo e
nenhuma métrica é recalculada no navegador.

Quem usa: o grupo, na apresentação do projeto, e a professora, para ver o preditor em ação.

### O que é real e o que é simulado

| Elemento na tela | Origem |
|---|---|
| Instante, RTT, timeout e perda de cada medição | real (`dataset_rotulado_B.parquet`) |
| `status_atual` e `status_futuro` | real (Gold) |
| Classe prevista | real (árvore oficial, mesma semente e hiperparâmetros de `arvore_oficial.json`) |
| Posição da sonda e do destino | aproximada (ver "Coordenadas") |
| Cabos submarinos e estações de aterragem | reais (existem), em traçado simplificado |
| **Caminho de cada fluxo por esses cabos** | **simulado**: o dataset é de ping, não tem traceroute |
| Distância e RTT mínimo teórico da rota | calculados sobre a rota simulada |

A página traz um aviso fixo e visível: "Rota ilustrativa: os cabos existem, mas o caminho de cada fluxo é simulado."

### Bloco exibido: validação

O replay usa só o bloco `validacao` (23/09 20:09 a 24/09 08:08, cerca de 14 mil medições, 12 h). O teste continua
fechado até a Tarefa 5 (decisão de `AGENTS.md`): o exportador recusa o bloco `teste`. Depois da Tarefa 5, trocar o
bloco é decisão do dono e exige rever as checagens de `visualizacao/execucao.py`, que hoje comparam com a validação.

Medições sem `status_futuro` (lacuna na coleta) e as 3 últimas de cada fluxo (folga) aparecem no mapa, mas sem
previsão conferida: o cartão mostra "sem futuro para conferir". Elas não entram no placar.

### Rota simulada

A rota é plausível do ponto de vista de redes (decisão do dono, 01/10/2026: a página também serve à disciplina de
Redes de Computadores): ela segue por terra até uma estação de aterragem, cruza o oceano por um **cabo submarino
que existe** e volta a seguir por terra até o destino. Não é o caminho que os pacotes fizeram.

- A rota de um fluxo é uma lista de **trechos**, cada um com um tipo:
  - `terrestre`: backbone por terra entre cidades (ex.: sonda → São Paulo → Fortaleza; Sines → Madri → Frankfurt);
  - `submarino`: um cabo real, com nome, entre duas estações de aterragem (ex.: EllaLink, Fortaleza → Sines).
- Os nós da rota também têm tipo: `sonda`, `pop` (cidade ou ponto de troca de tráfego, como o IX.br São Paulo ou o
  DE-CIX Frankfurt), `aterragem` (estação onde o cabo chega à costa) e `destino`.
- Um catálogo pequeno e escrito à mão em `config.py` lista os cabos usados (cerca de 8), com nome, estações de
  aterragem e alguns pontos intermediários no mar, para a linha não cortar continentes. Candidatos, a conferir um a
  um na fonte durante o build (mapa público da TeleGeography, submarinecablemap.com):
  - Brasil → Europa: EllaLink (Fortaleza – Sines);
  - Brasil → América do Norte: Monet (Santos – Fortaleza – Boca Raton), Seabras-1 (Praia Grande – Nova Jersey);
  - América do Norte → Ásia: FASTER (Oregon – Japão), JUPITER (Califórnia – Japão);
  - Japão → Singapura: SJC;
  - destinos no Brasil: só trechos terrestres.
- Para cada região de destino há 1 a 3 rotas possíveis. A escolha usa a semente do projeto (`SEMENTE = 16`)
  combinada com o `fluxo_id`: o mesmo fluxo desenha sempre a mesma rota, em qualquer execução.
- A rota é gerada no exportador (Python), não no navegador, e vai dentro do JSON.
- **Distância e RTT mínimo:** o exportador soma o comprimento da rota (distância em círculo máximo de cada trecho)
  e calcula o RTT mínimo teórico de ida e volta na fibra (cerca de 200 km por ms, 2/3 da velocidade da luz). O
  painel do fluxo mostra "rota simulada: N km, RTT mínimo teórico X ms" ao lado da mediana real do baseline. É um
  número didático; não entra no modelo nem no rótulo.

Na tela, o trecho terrestre é uma linha cheia e o submarino uma linha tracejada com o nome do cabo; ao passar o
mouse (ou tocar) em um trecho, aparecem o tipo, o nome e o comprimento. Uma legenda fixa explica os quatro tipos de
nó e os dois tipos de trecho.

### Coordenadas

- **Destino:** o dataset só tem o país (BR, JP, SG, US, DE, PT). Cada país vira um ponto fixo (uma cidade), com um
  pequeno deslocamento por `dst_addr` para os destinos do mesmo país não ficarem empilhados.
- **Sonda:** ver "Perguntas em aberto" (1).

### Comportamento da página

1. **Mapa:** projeção plana do mundo em traço, com sondas, saltos e destinos marcados.
2. **Pulso:** a cada medição, um pulso percorre os saltos na ida e na volta. A duração na tela é proporcional ao RTT
   real (com piso e teto, para continuar visível). Em timeout, o pulso para no meio da rota e some.
3. **Cor:** o arco do fluxo assume a cor do `status_atual` da medição (OK verde, RISCO amarelo, FALHA vermelho).
4. **Previsão:** quando o pulso volta, o fluxo ganha um selo "PREVISTO: <classe> em 12 min".
5. **Conferência:** quando o relógio do replay chega ao instante do futuro, o selo vira "ACERTOU" ou "ERROU"
   (previsto × `status_futuro`).
6. **Painel lateral:**
   - relógio do replay (data e hora reais da medição) e velocidade;
   - placar acumulado da árvore e da persistência (acertos / conferidas), lado a lado;
   - matriz 3×3 acumulada da árvore;
   - feed das últimas previsões conferidas;
   - ao clicar em um fluxo: as 8 colunas do X da última medição e a regra em português da folha que decidiu.
7. **Controles:** tocar / pausar, velocidade (60×, 300×, 900×), barra de tempo para pular, filtro por região.

Ao fim do replay, o placar e a matriz da página têm de bater com `metricas_validacao.csv` e
`matriz_validacao.csv` (descontadas as mesmas linhas de folga). Essa é a principal checagem.

### Visual: neo-brutalismo

- Fundo creme chapado, bordas pretas de 3 a 4 px, cantos retos.
- Sombras duras e deslocadas (sem desfoque), cartões levemente desalinhados.
- Tipografia pesada, sem serifa, em caixa alta nos títulos; números em monoespaçada.
- Cores chapadas e saturadas, sem gradiente. As três classes sempre acompanhadas de texto ou forma (nunca só cor).
- Mapa em traço preto sobre fundo liso; saltos como quadrados com borda; destinos como círculos.

## Stack

- **Exportador:** Python 3.11, pandas + pyarrow + scikit-learn (já são dependências). Sem Spark, sem Java.
- **Página:** HTML + CSS + JavaScript puro, sem framework e sem etapa de build. D3 (`d3-geo`) e TopoJSON para o
  mapa, desenho dos pulsos em `<canvas>`.
- Sem backend: a página lê um JSON estático.

## Comandos

```bash
# gera o JSON do replay (offline; exige o Gold no disco):
uv run python -m preditor replay      # data/gold/ → web/dados/replay.json
# serve a página (só biblioteca padrão; Ctrl+C encerra):
uv run python -m preditor servir      # http://127.0.0.1:8000  (`--porta N` troca a porta)
```

`replay` é um comando à parte, como `arvore`: não entra na execução sem argumento. Sem o Gold, termina pedindo
`uv run python -m preditor gold`. `servir` também (sem Spark nem Java); sem `web/dados/replay.json`, pede `replay`.
Não se usa o `python -m http.server`: com vários navegadores ao mesmo tempo ele perdeu até 6,5 % dos arquivos
(HTTP/1.0 e fila de 5 conexões) e a página ficava presa em "Carregando o replay..." sem mensagem.

## Estrutura

```
src/preditor/visualizacao/
  __init__.py
  rotas.py        → saltos simulados e coordenadas (sonda, hubs, destino)
  exportacao.py   → monta as linhas do replay: medição + previsão + futuro
  execucao.py     → orquestra, grava o JSON e verifica
web/
  index.html
  estilo.css
  app.js          → relógio do replay, painel e controles
  mapa.js         → projeção, arcos e pulsos
  dados/          → replay.json (ignorado pelo git)
```

Constantes novas (bloco exibido, cidades-hub, pontos por país, piso e teto do pulso) vão para `config.py`, com a
origem comentada.

### Formato do `replay.json`

```json
{
  "meta": {"bloco": "validacao", "inicio": "...", "fim": "...", "classes": ["OK", "RISCO", "FALHA"],
           "aviso": "Rota ilustrativa: os cabos existem, mas o caminho de cada fluxo é simulado."},
  "fluxos": [{"id": "6602|129.143.66.65|23589837", "regiao": "Europa", "pais": "DE",
              "km": 11850, "rtt_minimo_ms": 118.5,
              "trechos": [
                {"tipo": "terrestre", "nome": "backbone BR", "km": 2400,
                 "nos": [{"tipo": "sonda", "nome": "sonda 6602", "ponto": [-46.6, -23.5]},
                         {"tipo": "aterragem", "nome": "Fortaleza", "ponto": [-38.5, -3.7]}]},
                {"tipo": "submarino", "nome": "EllaLink", "km": 6000,
                 "nos": [{"tipo": "aterragem", "nome": "Fortaleza", "ponto": [-38.5, -3.7]},
                         {"tipo": "aterragem", "nome": "Sines", "ponto": [-8.9, 37.9]}]}]}],
  "medicoes": [{"f": 0, "t": 1790280598, "rtt": 210.5, "timeout": 0,
                "atual": "OK", "previsto": "OK", "futuro": "OK", "folha": 12,
                "x": [0.64, 0.36, 0.11, 0.0, 0, 0, 0, 0]}],
  "regras": {"12": "se z_robusto ≤ 3,4100 e n5_moderado ≤ 1,5 então OK"}
}
```

## Estilo de código

Python segue o resto do pacote: português, passo a passo comentado, sem construções compactas. JavaScript também em
português, funções pequenas e nomeadas:

```js
// Avança o relógio do replay e solta os pulsos das medições que "aconteceram" neste quadro.
function avancarRelogio(estado, segundosReais) {
  estado.agora += segundosReais * estado.velocidade;
  while (estado.proxima < estado.medicoes.length && estado.medicoes[estado.proxima].t <= estado.agora) {
    soltarPulso(estado, estado.medicoes[estado.proxima]);
    estado.proxima += 1;
  }
}
```

## Verificação

Sem framework de testes: como nas outras partes, o comando termina com checagens automáticas.

- Nenhuma linha do bloco `teste` no JSON.
- A previsão exportada é idêntica à da árvore oficial: recalculando as métricas a partir do JSON (sem as linhas de
  folga e sem futuro nulo), F1 macro e matriz batem com `metricas_validacao.csv` e `matriz_validacao.csv`.
- Toda rota começa na sonda e termina no destino, com coordenadas válidas (lon de -180 a 180, lat de -90 a 90) e
  trechos encadeados (o último nó de um trecho é o primeiro do seguinte).
- Todo trecho `submarino` usa um cabo do catálogo e começa e termina em nó `aterragem`; rota para destino fora do
  Brasil tem ao menos um trecho submarino, e para destino no Brasil, nenhum.
- `km` da rota = soma dos trechos; `rtt_minimo_ms` = 2 × km / 200.
- Mesma semente = mesmo JSON (duas execuções, arquivos idênticos).
- Medições em ordem de `t`; todo `f` aponta para um fluxo existente; toda `folha` tem regra.

Página: conferência manual no navegador (replay até o fim, placar igual ao CSV; pausar, pular, filtrar; sem erro no
console; legível em tela de projetor e em janela estreita).

## Limites

- **Sempre:** avisar na tela que a rota é ilustrativa; usar só a validação; ler o Gold do disco; manter o
  navegador sem cálculo de métrica do X ou de rótulo.
- **Perguntar antes:** adicionar dependência Python ou biblioteca JS além de D3 / TopoJSON; trocar o bloco exibido;
  versionar qualquer arquivo de dados; mexer em `modelo/` além de reutilizar funções.
- **Nunca:** exibir ou exportar o bloco `teste` antes da Tarefa 5; usar região, país ou RTT absoluto como feature;
  apresentar os saltos como caminho real; commitar `web/dados/`.

## Critérios de sucesso

1. `uv run python -m preditor replay` gera `web/dados/replay.json` e passa em todas as checagens.
2. A página abre com um comando, toca o replay da validação inteira e mostra pulsos indo e voltando por rotas com
   trechos terrestres e cabos submarinos nomeados, distinguíveis na tela.
3. Cada medição conferível mostra previsto × aconteceu; o placar final bate com os CSVs da árvore.
4. O placar da persistência aparece ao lado do da árvore.
5. O visual segue o neo-brutalismo descrito e o aviso de rota ilustrativa está sempre visível.

## Decisões do dono (01/10/2026)

1. **Coordenadas das sondas:** consultadas uma única vez na API pública do RIPE Atlas (13 sondas) e gravadas em
   `src/preditor/visualizacao/sondas.csv`, versionado. O comando `replay` lê esse CSV e continua offline.
2. **D3, TopoJSON e contorno do mundo:** cópia local em `web/vendor/`, versionada. A página não usa internet.
3. **Árvore de contraste:** fica fora da página. Só a oficial e a persistência.
4. **Traçado dos cabos:** catálogo à mão (cerca de 8 cabos), cada um conferido na fonte durante o build.
5. **Skill `frontend-ui-engineering`:** não instalada por enquanto; o dono decide antes da tarefa V2 se quer.

## Mudanças durante a implementação (02/10/2026)

- **Formato do JSON:** cada trecho tem também `caminho` (a polilinha completa, com os pontos no mar); cada fluxo tem
  `opcao` (nome da rota) e `mediana_ms`; cada medição tem `conferivel`, `t_futuro`, `x` e `folha`; o documento tem
  `colunas` e `regras`. Os campos `sonda` e `destino` do fluxo não existem.
- **Escolha da rota:** o sorteio é só entre as opções fisicamente possíveis para o fluxo (RTT mínimo teórico ≤ mediana
  real). Destino do BR em Belo Horizonte; do US em Miami ou Nova York, inferido do RTT. Confirmado pelo dono em 02/10/2026.
- **Previsão no mapa:** em vez do texto "PREVISTO: <classe> em 12 min", cada fluxo tem um selo com a letra da classe
  (O, R, F), que vira ✓ ou ✗ por um instante ao conferir; o texto completo fica no feed e no cartão do fluxo.
- **Cartão do fluxo:** mostra também a última previsão já conferida (a última medição está sempre aguardando o futuro).
- **Servidor:** `uv run python -m preditor servir` substitui o `python -m http.server`, que perdia arquivos sob
  concorrência.
- **Mapa centrado em 105° O,** para nenhuma rota do Pacífico ser cortada pela borda.
- **Fora da spec original, acrescentados:** feed "só erros", lista de fluxos para telas estreitas, navegação por
  teclado nos selos, favicon e os textos de licença do vendor.
