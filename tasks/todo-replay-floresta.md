# Tarefas: Replay da apresentação com a Random Forest

Spec: `SPEC-replay-floresta.md`. Plano: `tasks/plan-replay-floresta.md`.
**Execução em lote único (R1 a R3);** o implementador faz tudo em sequência e para no checkpoint.

**REGRA DURA:** o implementador NUNCA lê o bloco `teste` do Gold, NUNCA roda `teste --abrir-o-teste` e NUNCA apaga
`data/modelo/teste/TESTE_ABERTO.json`. O `replay` usa só o bloco de validação.

**Paradas obrigatórias** (parar e relatar, sem afrouxar nada):
- o placar do JSON não bate com `comparacao_modelos.csv` / `matriz_comparacao.csv`;
- `arvore`, `ajuste`, `comparar`, `exportar` ou `teste --ensaio` mudam de saída;
- for preciso mexer em `execucao_teste.py` (o carimbo do ensaio muda) ou em qualquer coisa fora da lista de arquivos;
- qualquer necessidade de ler o bloco de teste.

Nada é commitado sem o dono pedir. Não mexer em `notebooks/02_post_medicoes_periodicas.ipynb` nem em
`.claude/agents/implementer.md`. Antes de mexer em código, copiar `data/modelo/` para `data/modelo_antes_replay/` e
`web/dados/replay.json` para `data/replay_antes_floresta.json`.

- [x] ✅ **R1: exportador e execução do replay com a floresta**
  - Descrição: ler o `.joblib` (SHA-256 conferido contra o `LEIA-ME.md`, família, colunas), prever todo o bloco de
    validação com o X de 10 colunas, exportar `previsto` da floresta e o bloco `modelo`; tirar `arvores`, `folha`, `x` e
    regras do JSON e o refazer de árvore e ajustada; trocar as checagens (spec, "Verificações"); `replay` deixa de exigir
    as saídas do `ajuste` e passa a exigir as do `exportar` e do `comparar`.
  - Aceite: `uv run python -m preditor replay` termina com todas as checagens; previsões do JSON = recarga do modelo;
    matriz e F1 do JSON = CSVs da comparação (F1 macro 0,6977, N = 13.490); nenhuma linha nem instante do teste; mesma
    entrada = mesmo JSON; o JSON não tem `arvores`, `folha` nem `x`.
  - Verificação: `replay` duas vezes (JSON idêntico); prova de que o placar recalculado bate; `grep` mostra que nenhum
    JS de `web/` lê os campos removidos.
  - Depende de: nada. Arquivos: `visualizacao/exportacao.py`, `visualizacao/execucao.py`, `config.py`, módulo novo de
    leitura do `.joblib` se preciso. Tamanho: L.

- [x] ✅ **R2: página com o nome do modelo**
  - Nota (10/10/2026): o fim do replay foi alcançado pela barra de tempo (tecla End), porque a aba do navegador embutido fica `hidden` e a animação não avança; o caminho de pular é o mesmo que o de tocar (conferido em Node).
  - Descrição: mostrar "Random Forest, N árvores" (de `modelo.nome` e `modelo.arvores`) no cabeçalho do placar, com
    `textContent`; garantir que a tela diga que o período é o de **validação** (texto existente ou novo); ajustar
    `web/verificar-carga.js` se ele checar campos removidos.
  - Aceite: no navegador embutido, a página abre sem erro no console, toca o replay até o fim e o placar final é igual ao do
    JSON e à comparação; largura de notebook (1366) e de tela grande (1920); CSP intacta; capturas de tela.
  - Depende de: R1. Arquivos: `web/index.html`, `web/app.js` e/ou `web/painel.js`, `web/estilo.css`,
    `web/verificar-carga.js`. Tamanho: M.

- [x] ✅ **R3: documentos e identidade**
  - Descrição: `AGENTS.md` (comando `replay`, requisitos, decisão), `SPEC-visualizacao.md` (nota datada),
    `SPEC-replay-floresta.md` (critérios com evidência); rodar `arvore`, `ajuste`, `comparar`, `exportar` e `teste --ensaio`
    e comparar com `data/modelo_antes_replay/`.
  - Aceite: `diff -rq` vazio (fora de `comparacao/tempos.csv`, coluna `segundos`, e de `teste/ensaio_ok.json` só se o
    código de medição não mudou); critérios 1 a 5 da spec marcados.
  - Depende de: R2. Arquivos: `AGENTS.md`, `SPEC-visualizacao.md`, `SPEC-replay-floresta.md`. Tamanho: S.

### Checkpoint: fim do lote
- [ ] `replay` passa; página confere (placar = JSON = comparação); console limpo
- [ ] Os outros comandos idênticos; teste fora do JSON
- [ ] Capturas de tela e relatório do implementador
- [ ] Revisão do dono; commit só se ele pedir
