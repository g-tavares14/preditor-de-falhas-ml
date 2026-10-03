# Plano: árvore na página

Spec: [`SPEC-arvore-na-pagina.md`](../SPEC-arvore-na-pagina.md)

## Componentes e ordem

1. **Estrutura da oficial no JSON** (Python): exportar os 31 nós de `tree_` (coluna, limiar, `ausente_vai`, filhos,
   pai, classe, N por classe). Checagem: percorrer a estrutura com o `x` de cada medição dá a `folha` já exportada.
   Base de tudo; não depende da ajustada.
2. **Painel com a oficial** (página): `web/caminho.js` (lógica pura: folha → caminho pelos pais) e `web/arvore.js`
   (diagrama D3 + caminho aceso do fluxo em foco, com valor × limiar e lista em texto). Fatia vertical já demonstrável.
3. **Ajustada no JSON** (Python): refazer a ajustada no `replay` (conferida contra `arvore_ajustada.json` e as
   métricas da Tarefa 4), exportar a estrutura dela, e por medição `folha_ajustada`, `previsto_ajustada` e `x_ajuste`
   (`min5_z`, `media5_z`). Mesma checagem de percurso.
4. **Seletor** (página): alterna a árvore do painel; mapa, cartões e placar ficam na oficial.
5. **Docs**: `AGENTS.md` (decisões e checagens do replay), `README.md`, `SPEC-visualizacao.md` (aponta para esta spec).

1 → 2 e 1 → 3 são independentes entre si; 4 depende de 2 e 3.

## Riscos

- **Ausente na divisão:** o scikit-learn guarda o lado do NaN por nó (`missing_go_to_left`); exportar errado faria o
  texto da página mentir. Mitigação: a checagem de percurso usa linhas com ausente.
- **Peso de classe na ajustada:** `tree_.value` vem ponderado; o N por classe exportado deve descontar o peso (como
  `Regras.verificar` já faz).
- **Refazer a ajustada no `replay`:** reutilizar `modelo/ajuste.py` sem mudar saídas do `ajuste`; se precisar de
  função nova, ela só lê.
- **Espaço na tela:** 16 folhas lado a lado em ~400 px. Mitigação: folha como marcador pequeno + rótulo da classe; nó
  com texto curto e detalhe no caminho aceso.

## Checkpoints

- Após 1: `replay` passa com as checagens novas.
- Após 2: página abre sem erro no console, caminho aceso confere com o cartão.
- Após 4: as duas árvores no seletor; `arvore` e `ajuste` com saídas idênticas.
