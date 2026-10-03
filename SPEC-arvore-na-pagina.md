# Spec: Árvore na página (simulação da árvore no replay)

Status: **aprovada pelo dono em 03/10/2026**; as perguntas em aberto seguiram a recomendação (seletor só no painel; painel desce em tela estreita; nenhuma skill nova).

## Avaliação: é possível?

Sim, e com pouco custo. As duas árvores têm profundidade 4 e 16 folhas, ou seja, **31 nós** (15 divisões + 16
folhas): cabe num diagrama pequeno, sem rolagem, ao lado do mapa. O que já existe:

- o `replay.json` já traz, por medição, a `folha` da árvore oficial e os valores `x` das 8 colunas;
- já traz o texto da regra de cada folha (`regras`);
- falta só a **estrutura** da árvore (cada nó: coluna, limiar, para onde vai o ausente, filhos, classe e N por classe)
  e, para a ajustada, a folha, a previsão e as 2 colunas novas (`min5_z`, `media5_z`) de cada medição.

O navegador continua sem calcular nada (decisão de `AGENTS.md`): ele **não percorre a árvore com o `x`**; recebe a
folha pronta do JSON e acende o caminho raiz → folha subindo pelos pais. O Python confere que percorrer a estrutura
exportada com o `x` chega na mesma folha do `apply` do scikit-learn.

## Objetivo

Mostrar, ao lado do mapa, a árvore de decisão "funcionando": ao selecionar um fluxo, o diagrama acende o caminho que a
medição atual desse fluxo percorreu, com o valor de cada coluna ao lado do limiar de cada nó, até a folha que deu a
previsão. Um seletor alterna entre a árvore oficial (Tarefa 3) e a ajustada (Tarefa 4).

Quem usa: o grupo, na apresentação, e a professora, para ver *por que* a árvore previu aquela classe.

## Decisões do dono (03/10/2026)

1. **As duas árvores, com seletor** (oficial e ajustada).
2. **Painel ao lado do mapa**, sempre visível.
3. **Animação: caminho do fluxo em foco**, com o valor de cada coluna ao lado do limiar. (Contagem por folha e
   espessura das arestas ficaram de fora.)

## Comportamento

1. O painel mostra os 31 nós em camadas (raiz no topo). Nó de divisão: `coluna ≤ limiar`. Folha: classe prevista
   (cor da classe, a mesma do mapa) e N do treino.
2. Sem fluxo em foco: árvore em repouso, sem caminho aceso.
3. Com fluxo em foco: a cada nova medição desse fluxo, o caminho raiz → folha acende; em cada nó do caminho aparece o
   valor da coluna (ex.: `z_robusto = 1,37 ≤ 2,02 → sim`). Valor ausente aparece como "ausente → esquerda/direita",
   seguindo o lado que o nó guardou no treino.
4. A folha acesa mostra a regra em português (o texto já exportado) e, quando o relógio passa de `t_futuro`, se acertou.
5. O seletor troca a árvore do painel. **Mapa, cartões e placar continuam na árvore oficial** (ver Pergunta 1).
6. Teclado e leitor de tela: o caminho aceso também sai como texto (lista dos passos), não só como cor.

## Mudanças por camada

| Onde | O quê |
|---|---|
| `visualizacao/exportacao.py` | exporta `arvores: {oficial, ajustada}`, cada uma com `nos` (id, pai, coluna, limiar, `ausente_vai`, filhos, classe, N por classe), `colunas` e `regras`; por medição, `folha_ajustada`, `previsto_ajustada` e os valores de `min5_z` e `media5_z` |
| `visualizacao/execucao.py` | refaz a ajustada (conferida contra `arvore_ajustada.json`) e acrescenta as checagens abaixo |
| `web/arvore.js` (novo) | desenho do diagrama e do caminho aceso (D3 já vendorizado) |
| `web/caminho.js` (novo, lógica pura) | folha → lista de nós do caminho, só subindo pelos pais; roda em Node |
| `web/app.js`, `index.html`, `estilo.css` | painel, seletor e ligação com o fluxo em foco |

O `arvore` e o `ajuste` não mudam. O `replay.json` cresce cerca de 0,5 MB (hoje 2,7 MB).

## Comandos

```bash
uv run python -m preditor replay   # refaz as duas árvores, confere e grava web/dados/replay.json
uv run python -m preditor servir   # abre em http://127.0.0.1:8000/
node web/caminho.js                # se tiver auto-checagem, como tempo.js/placar.js
```

## Verificação (checagens automáticas no `replay`)

- Estrutura exportada de cada árvore tem 31 nós, 16 folhas, e é a mesma de `tree_` (coluna, limiar, filhos).
- Percorrer a estrutura exportada com o `x` de cada medição (em Python, caminho independente do `apply`) dá a mesma
  folha do JSON, nas duas árvores; ausente segue `ausente_vai`.
- A classe de cada folha exportada = a previsão das medições que caem nela.
- Ajustada refeita = `arvore_ajustada.json`; matriz e F1 dela recalculados do JSON = `matriz_ajuste.csv` /
  `metricas_ajuste.csv`.
- `x` com exatamente as 8 colunas da oficial; as 2 da ajustada em campo separado (a checagem atual "`x` só com as 8
  colunas" continua valendo).
- Nenhuma linha nem instante do teste; mesma semente = mesmo JSON.
- Página: ao focar um fluxo, o caminho aceso termina na folha da medição atual; com o seletor em "ajustada", termina
  em `folha_ajustada`.

## Boundaries

- **Sempre:** o navegador só exibe o que veio do JSON; números mágicos de desenho no topo do módulo JS; sem `innerHTML`
  com dados; CSP `default-src 'self'`; textos em português.
- **Perguntar antes:** mudar a árvore do mapa/placar; abrir o bloco de teste; nova dependência ou CDN.
- **Nunca:** recalcular previsão ou métrica no navegador; alterar `modelo/` de forma que mude as saídas do `arvore` ou
  do `ajuste`.

## Critérios de sucesso

- O painel mostra as duas árvores (seletor), 31 nós cada, legíveis a 1280 px de largura sem rolagem.
- Para qualquer fluxo em foco, o caminho aceso e os valores batem com a folha e o `x` do JSON.
- Todas as checagens do `replay` passam; `arvore` e `ajuste` com saídas idênticas às de antes.

## Perguntas em aberto

1. **O seletor muda só o painel, ou também mapa, cartões e placar?** Recomendo só o painel (o `AGENTS.md` diz que o
   replay continua na árvore da Tarefa 3, e o placar ficaria com dois resultados). Mudar tudo exige rever essa decisão.
2. **Em tela estreita** (celular), o painel vai para baixo do mapa ou some? Recomendo ir para baixo.
3. Skill do catálogo: `frontend-ui-engineering` (painel novo, acessibilidade) se encaixa. Quer adicionar?

## Mudanças durante a implementação (03/10/2026)

- **Acerto no painel:** o painel mostra a previsão da última medição, não se ela acertou (o futuro dela ainda não
  chegou); a última previsão conferida continua no cartão do fluxo. O item 4 de "Comportamento" fica assim.
- **Posição:** o painel ocupa a largura inteira, abaixo do mapa e dos painéis; a página passa a rolar na vertical.
- **Tamanho:** o `replay.json` cresce cerca de 1 MB (2,7 → 3,75 MB), não 0,5 MB.
- **Limiar no JSON:** 6 casas (`CASAS_LIMIAR_REPLAY` em `config.py`), conferido pelo percurso nos nós.
- **Validação na página:** `tempo.js` recusa um JSON sem `arvores` ou sem os campos da ajustada, com a dica de rodar o
  `replay` de novo.

