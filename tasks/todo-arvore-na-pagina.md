# Tarefas: árvore na página

Plano: [`plan-arvore-na-pagina.md`](plan-arvore-na-pagina.md) · Spec: [`SPEC-arvore-na-pagina.md`](../SPEC-arvore-na-pagina.md)

Verificação padrão: `uv run python -c "import preditor.__main__"`, `uv run python -m preditor replay` e, nas tarefas
de página, `uv run python -m preditor servir` com o console do navegador sem erro.

---

## ✅ A1: Estrutura da árvore oficial no JSON

**Descrição:** Em `visualizacao/exportacao.py`, exportar `arvores.oficial` com `colunas`, `regras` (as que já existem)
e `nos`: `id`, `pai`, `coluna`, `limiar`, `ausente_vai` (`esquerda`/`direita`), `esquerda`, `direita`, `classe`
(folhas) e `n` por classe. Manter `regras` e `x` atuais compatíveis com a página.

**Critérios de aceite:**
- [ ] 31 nós, 16 folhas; coluna, limiar e filhos = `tree_`
- [ ] Checagem nova em `visualizacao/execucao.py`: percorrer `nos` com o `x` de cada medição (caminho independente de
      `apply`) chega na `folha` exportada; inclui linhas com ausente
- [ ] Classe de cada folha = `previsto` das medições que caem nela
- [ ] Demais checagens do `replay` passam; mesma semente = mesmo JSON

**Verificação:** `uv run python -m preditor replay`; `uv run python -m preditor arvore` inalterado
**Dependências:** nenhuma
**Arquivos:** `src/preditor/visualizacao/exportacao.py`, `src/preditor/visualizacao/execucao.py`
**Escopo:** pequeno

## ✅ A2: Painel com a árvore oficial e caminho do fluxo em foco

**Descrição:** `web/caminho.js` (puro, sem DOM: `caminho(nos, folha)` sobe pelos pais) e `web/arvore.js` (diagrama em
camadas com D3 de `web/vendor/`). Com fluxo em foco, acende o caminho da medição atual e mostra `coluna = valor ≤
limiar → sim/não` (ausente: "ausente → lado"); a folha mostra a regra e, após `t_futuro`, acerto/erro. Lista em texto
do caminho para leitor de tela. Em tela estreita, o painel desce para baixo do mapa.

**Critérios de aceite:**
- [ ] Nenhum cálculo de previsão no navegador; sem `innerHTML` com dados; constantes de desenho comentadas no topo
- [ ] Caminho aceso termina na `folha` da medição atual; cores das classes = as do mapa
- [ ] Legível a 1280 px sem rolagem; abaixo do mapa em tela estreita
- [ ] `caminho.js` roda em Node

**Verificação:** `servir`, focar 2–3 fluxos (um com valor ausente) e conferir com o cartão; console sem erro
**Dependências:** A1
**Arquivos:** `web/caminho.js`, `web/arvore.js`, `web/app.js`, `web/index.html`, `web/estilo.css`
**Escopo:** médio

### Checkpoint 1: dono vê a árvore oficial funcionando na página

## ✅ A3: Árvore ajustada no JSON

**Descrição:** No `replay`, refazer a ajustada (`MODELO_AJUSTADA`, mesma semente), conferir contra
`arvore_ajustada.json`, exportar `arvores.ajustada` (mesmo formato de A1, N por classe sem o peso) e, por medição,
`folha_ajustada`, `previsto_ajustada` e `x_ajuste` (`min5_z`, `media5_z`).

**Critérios de aceite:**
- [ ] Hiperparâmetros e peso = `arvore_ajustada.json`; matriz e F1 do JSON = `matriz_ajuste.csv`/`metricas_ajuste.csv`
- [ ] Checagem de percurso de A1 também para a ajustada (com `x` + `x_ajuste`)
- [ ] `x` continua com só as 8 colunas; `ajuste` com saídas idênticas
- [ ] Mesma semente = mesmo JSON; nenhum instante do teste

**Verificação:** `uv run python -m preditor replay`; `uv run python -m preditor ajuste` e diff das saídas
**Dependências:** A1 (pode correr em paralelo com A2)
**Arquivos:** `src/preditor/visualizacao/exportacao.py`, `src/preditor/visualizacao/execucao.py`, `src/preditor/config.py` (se precisar)
**Escopo:** médio

## ✅ A4: Seletor oficial / ajustada

**Descrição:** Seletor no painel que troca a árvore desenhada e o caminho (usa `folha_ajustada` e `x_ajuste`). Mapa,
cartões e placar continuam na oficial; o painel diz qual árvore está à mostra.

**Critérios de aceite:**
- [ ] Trocar a árvore mantém o fluxo em foco e acende o caminho certo na hora
- [ ] Placar e cartões não mudam ao trocar
- [ ] Acessível por teclado

**Verificação:** `servir`, alternar com fluxo em foco e conferir as duas folhas; console sem erro
**Dependências:** A2, A3
**Arquivos:** `web/arvore.js`, `web/app.js`, `web/index.html`, `web/estilo.css`
**Escopo:** pequeno

## ✅ A5: Documentação

**Descrição:** Atualizar `AGENTS.md` (estágio, decisões, checagens do replay, arquivos de `web/`), `README.md` e
`SPEC-visualizacao.md` (referência a esta spec).

**Critérios de aceite:**
- [ ] Decisão "seletor só no painel" registrada; checagens novas listadas

**Verificação:** leitura
**Dependências:** A4
**Arquivos:** `AGENTS.md`, `README.md`, `SPEC-visualizacao.md`
**Escopo:** pequeno

### Checkpoint final: dono revisa antes de commitar
