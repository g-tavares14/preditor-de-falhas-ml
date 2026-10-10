# Spec: Replay da apresentação com a Random Forest

Status: **aprovada pelo dono (10/10/2026); implementada em R1 a R3 no mesmo dia, com as evidências abaixo.**

## Objetivo

A página da apresentação (`web/`, já simplificada para público não técnico e na `main`) passa a mostrar as previsões da
**Random Forest** escolhida na comparação (`data/modelo/exportado/modelo_final.joblib`), e não mais as da árvore da
Tarefa 3. Continua sendo um **replay pré-calculado do bloco de validação**, estático e offline: o navegador só exibe,
compara e soma o que está no JSON. Decisões do dono (10/10/2026): replay com a floresta (não ao vivo) e período = validação.

### O que não muda

- A página (HTML, CSS, JS) e as rotas: só ganha o nome do modelo na tela (ver abaixo).
- O bloco exibido (`validacao`), o `t_futuro`, as rotas simuladas, o placar contra o "palpite simples" (persistência),
  as regras do exportador de nunca incluir linha ou instante do teste.
- `arvore`, `ajuste`, `comparar`, `exportar` e `teste` e as saídas deles: byte a byte iguais.
- O teste continua como está (aberto e medido uma vez). O replay não o lê.

## Mudança

1. **`previsto` vem da floresta.** O `replay` carrega o `modelo_final.joblib` (SHA-256 conferido contra o `LEIA-ME.md`,
   como o `teste`), monta o X de 10 colunas do bloco exibido (`DadosModelo.x_ajustado` / as colunas do `.joblib`) e prevê
   todas as medições do bloco (as não conferíveis também), com `NaN` como `NaN`.
2. **O JSON perde o que era só da árvore** e a página não usa: `arvores`, `folha`, `x` e as regras. Ganha um bloco
   `modelo` pequeno (nome, família, parâmetros, SHA-256, colunas, N de árvores) para a página mostrar "Modelo: Random Forest
   (100 árvores)". O `replay` deixa de refazer a árvore e a ajustada (some o passo de ~50 s) e de exigir as saídas do
   `ajuste`; exige as do `exportar` e do `comparar`.
3. **A página mostra o nome do modelo** num ponto discreto (cabeçalho do placar), lido do JSON, sem `innerHTML` com dados.

## Verificações automáticas (substituem as da árvore)

- O `.joblib` tem o SHA-256 do `LEIA-ME.md`; família = floresta; colunas = as do `.joblib`.
- As previsões do JSON = as do modelo recarregado, linha a linha; sem `NaN` imputado.
- **Placar do JSON = o da comparação:** a matriz e o F1 macro recalculados do JSON (nas conferíveis) são iguais às linhas
  `random_forest` e `persistencia` de `comparacao/matriz_comparacao.csv` e `comparacao_modelos.csv` (F1 macro 0,6977;
  N = 13.490).
- Mantidas, sem mudança: nenhuma linha nem instante do teste no JSON, `t_futuro` por caminho independente, rotas
  (começam na sonda, terminam no destino, só usam cabo do catálogo), mesma semente = mesmo JSON.
- A página, aberta no navegador, termina o replay com o placar igual às contagens do JSON, sem erro no console.

## Estrutura

```
src/preditor/visualizacao/exportacao.py   → previsão pelo .joblib; sem folhas, regras nem estrutura da árvore
src/preditor/visualizacao/execucao.py     → carrega e confere o modelo; checagens novas; remove as da árvore
src/preditor/config.py                    → só o que for preciso (origem comentada)
web/index.html, web/app.js (ou painel.js) → nome do modelo na tela
AGENTS.md, SPEC-visualizacao.md           → decisão e comandos
```

## Comandos

```bash
uv run python -m preditor exportar   # se ainda não existir o .joblib
uv run python -m preditor replay     # web/dados/replay.json com as previsões da floresta
uv run python -m preditor servir     # http://127.0.0.1:8000/ (use este, não `python -m http.server`)
```

Offline, sem Spark nem Java. Para a apresentação basta o `servir` com o `replay.json` já gerado; nada de modelo precisa
rodar durante a apresentação.

## Limites

- **Sempre:** `servir` só em `127.0.0.1`; sem `innerHTML` com dados; CSP `default-src 'self'`; português; sem commit sem pedido.
- **Perguntar antes:** ler o bloco de teste; mudar o `modelo_final.joblib`; apagar a ligação com `arvore`/`ajuste` (eles
  seguem como estão).
- **Nunca:** imputar `NaN`; calcular métrica ou rótulo no navegador; expor o `.joblib` pelo servidor da página.

## Riscos

1. **O placar da página (floresta, 0,698 de F1 macro na validação) difere do número do teste (0,670) no relatório.**
   A página deve dizer que é a validação (o texto da tela já fala em "período reproduzido"; conferir) para não confundir a plateia.
2. **Tirar `arvores`, `folha` e `x` do JSON é uma mudança de formato.** Mitigação: a página já não os usa (conferido no
   merge de hoje); o `verificar-carga.js` e as checagens do exportador são ajustados.
3. **O replay deixa de conferir contra a árvore.** Compensado pelas checagens novas contra `comparacao_modelos.csv`.
4. **Floresta mais lenta para prever** (0,04 s para 13 mil medições): irrelevante para um replay pré-calculado.

## Critérios de sucesso

1. ✔ `replay` termina com todas as checagens e grava o JSON com as previsões da floresta: 14.096 medições, 79 fluxos; duas rodadas seguidas e uma depois da identidade dão o mesmo SHA-256 (4352479a…).
2. ✔ Placar ao fim do replay: 13.490 conferidas; floresta 11.535 acertos (85,5 %); persistência 11.018 (81,7 %). A matriz da floresta é a linha `random_forest` de `matriz_comparacao.csv`; F1 macro 0,6977 (floresta) e 0,6355 (persistência) conferidos pelo `replay`. A página não mostra o F1, só os acertos. Igual em `tocar` (Node) e em `pular` até o fim.
3. ✔ Página com "Random Forest, 100 árvores", console sem nenhuma mensagem, sem rolagem em 1366×768 e 1920×1080. Capturas em `tasks/capturas-replay/` (a resolução é a que a ferramenta do navegador entrega). Como a aba embutida fica `hidden` (a animação não avança), o relógio foi levado ao fim pela barra (tecla End), que chama o mesmo caminho de pular.
4. ✔ `arvore`, `ajuste`, `comparar`, `exportar` (exit 0) e `teste --ensaio` (`ensaio_ok.json` idêntico); `diff -rq` só em `comparacao/tempos.csv` (coluna `segundos`). `teste --abrir-o-teste` não foi rodado; o teste segue fora do JSON.
5. ✔ `AGENTS.md` e `SPEC-visualizacao.md` atualizados em 10/10/2026.

## Perguntas em aberto

1. Posso remover do JSON `arvores`, `folha` e `x` (a página não os usa)? Suposição: sim. Se quiser deixar a porta aberta
   para voltar a mostrar a árvore, o contrário é manter e só trocar o `previsto`, ao custo de continuar refazendo as
   árvores no `replay`.
2. O nome do modelo na tela deve aparecer? Suposição: sim, discreto ("Random Forest, 100 árvores").

Respostas do dono (10/10/2026): 1, sim (removidos); 2, sim.
