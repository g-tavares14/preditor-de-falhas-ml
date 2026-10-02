# Plano de implementação: visualização (replay no mapa-múndi)

Spec: [`SPEC-visualizacao.md`](../SPEC-visualizacao.md) (aprovada em 01/10/2026). Tarefas detalhadas em
[`todo-visualizacao.md`](todo-visualizacao.md). Os planos anteriores continuam em `plan.md` / `todo.md` (medalhão),
`plan-calculo-y.md` / `todo-calculo-y.md` (Y) e `plan-arvore.md` / `todo-arvore.md` (árvore).

## Visão geral

O projeto ganha o comando `uv run python -m preditor replay`, que lê o Gold, refaz a árvore oficial e grava
`web/dados/replay.json`, e uma página estática em `web/` que reproduz o bloco de validação em tempo acelerado: pulsos
indo e voltando por rotas simuladas (trechos terrestres e cabos submarinos reais), com a previsão da árvore para 12
min à frente e a conferência quando esse futuro chega. O visual é neo-brutalista. Cada tarefa deixa o comando rodando
e a página abrindo.

## Decisões de arquitetura

- **Pasta nova `src/preditor/visualizacao/`**, fora do medalhão e fora de `modelo/`: `rotas.py`, `exportacao.py` e
  `execucao.py` (`ExecucaoReplay`: orquestra, grava e verifica). `__main__.py` só ganha a opção `replay`, desviada
  antes de `build_spark`, como `arvore`. Sem Spark e sem Java.
- **A árvore é refeita, não lida do disco.** `arvore` não grava o modelo treinado (só a descrição em JSON). O
  `replay` chama `DadosModelo().carregar()` e `Arvore().buscar(dados)`: com a semente 16 o resultado é a mesma
  árvore. A checagem confere os hiperparâmetros escolhidos contra `arvore_oficial.json`; se diferirem, o comando
  para e pede `uv run python -m preditor arvore`. `modelo/` só é reutilizado, não alterado.
- **O exportador lê a validação inteira, não só as linhas mantidas pelo `DadosModelo`.** O mapa mostra todas as
  medições; a marca `conferivel` (futuro preenchido e fora da folga) decide quais entram no placar. A marca usa a
  mesma regra de `DadosModelo` (folga antes do filtro de nulos), e a checagem confere que o número de conferíveis é
  igual ao N da validação do `DadosModelo`.
- **O teste nunca é lido para dentro do JSON:** o exportador filtra `bloco == config.BLOCO_REPLAY` logo depois da
  leitura e a checagem recusa qualquer linha de `teste`.
- **Fatia fina primeiro (V1 + V2).** A primeira versão usa rota em linha reta e um ponto provisório para as sondas.
  O dono vê pulso no mapa antes de qualquer trabalho com cabos.
- **Rotas no Python, desenho no navegador.** O catálogo de cabos, os pontos por país e os hubs ficam em `config.py`
  com a origem comentada. O navegador só desenha o que vem no JSON e soma o placar: não calcula métrica do X nem
  rótulo.
- **Coordenadas das sondas em CSV versionado** (`src/preditor/visualizacao/sondas.csv`, 13 linhas), gerado uma vez
  por um script à parte que consulta a API pública do RIPE Atlas (sem chave). O `replay` só lê o CSV.
- **Página sem build:** `index.html`, `estilo.css`, `app.js`, `mapa.js`; D3, TopoJSON e o contorno do mundo em
  `web/vendor/`. Servida por `uv run python -m preditor servir` (`ThreadingHTTPServer`, HTTP/1.1, fila de 128; o `python -m http.server`
  perdia arquivos sob concorrência).
- **Pulsos em `<canvas>`**, mapa-base em SVG. Em 900× são cerca de 300 pulsos novos por segundo: canvas aguenta,
  SVG com um elemento por pulso não.
- **Projeção girada para nenhuma rota cruzar a borda do mapa.** As rotas para a Ásia cruzam o Pacífico; com o mapa
  centrado em Greenwich elas seriam cortadas. O corte da projeção fica onde nenhum trecho passa (decidido em V4,
  mostrado ao dono no checkpoint B).
- **`web/dados/` ignorado pelo git** (entra no `.gitignore` em V1).

## Ordem e dependências

```
V1 comando `replay` + JSON mínimo (medições, previsão, rota reta)
 └─ V2 página mínima: mapa, pulsos, relógio, tocar / pausar     ← checkpoint A (dono vê o pulso)
     ├─ V3 sondas + catálogo de cabos + rotas em trechos
     │   └─ V4 página desenha trechos, legenda e detalhes       ← checkpoint B (dono confere as rotas)
     └─ V5 previsão, conferência e placar
         └─ V6 painel do fluxo e controles
             └─ V7 acabamento visual e responsividade
                 └─ V8 documentação e fechamento                ← checkpoint C
```

V3 → V4 (rotas) e V5 → V6 (preditor) são independentes entre si, mas ambas mexem em `app.js`: faça em sequência.

## Lista de tarefas

### Fase 1: fatia fina
- [x] V1: Comando `replay` e JSON mínimo
- [x] V2: Página mínima com pulsos

### Checkpoint A (revisão do dono)
- [x] Pulsos indo e voltando no mapa, no tempo do replay; estilo-base aprovado

### Fase 2: rotas
- [x] V3: Sondas, catálogo de cabos e rotas em trechos
- [x] V4: Página desenha trechos terrestres e submarinos

### Checkpoint B (revisão do dono)
- [ ] Rotas e cabos conferidos; corte da projeção aprovado

### Fase 3: o preditor em cena
- [x] V5: Previsão, conferência e placar
- [x] V6: Painel do fluxo e controles

### Fase 4: fechamento
- [x] V7: Acabamento visual e responsividade
- [x] V8: Documentação e fechamento

### Checkpoint C (revisão do dono)
- [ ] Replay completo; placar da página = CSVs da árvore; critérios de sucesso da spec

## Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Nome ou estação de aterragem de um cabo errado (o catálogo parte de memória) | Alto: a página serve à aula de redes | V3 confere cada cabo no mapa da TeleGeography e anota a fonte em `config.py`; cabo não confirmado sai do catálogo |
| Placar da página não bate com os CSVs (folga, futuro nulo) | Alto | A marca `conferivel` é checada no Python contra o N do `DadosModelo` (V1); a página só soma |
| A árvore refeita difere da gravada | Médio | Checagem contra `arvore_oficial.json` em V1 |
| Sem rede para a API do Atlas ou para baixar D3 | Médio | São dois downloads únicos (V2 e V3); se falharem, parar e avisar o dono. Depois disso tudo roda offline |
| Rota cruzando a borda do mapa | Médio | Projeção girada (V4), conferida no checkpoint B |
| Canvas lento em 900× | Baixo | Teto de pulsos simultâneos; em velocidade alta o pulso encurta |
| Coordenada da sonda ausente ou genérica na API | Baixo | O script lista as sondas sem coordenada e o dono decide o ponto |

## Perguntas em aberto

- Instalar a skill `frontend-ui-engineering` antes de V2? (o dono decide; o plano não depende dela)
