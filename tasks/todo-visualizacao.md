# Tarefas: visualização (replay no mapa-múndi)

Plano: [`plan-visualizacao.md`](plan-visualizacao.md) · Spec: [`SPEC-visualizacao.md`](../SPEC-visualizacao.md)

Verificação padrão de toda tarefa (o projeto não tem testes nem linter): `uv run python -c "import preditor.__main__"`,
`uv run python -m preditor replay` (offline, sem Spark nem Java, a partir do Gold que já está no disco) e, nas tarefas
de página, abrir `http://127.0.0.1:8000` com `uv run python -m preditor servir` (não o `python -m http.server`, que perde arquivos
sob concorrência) e conferir que o console do navegador não tem erro.

---

## ✅ V1: Comando `replay` e JSON mínimo

**Descrição:** Criar `visualizacao/exportacao.py` e `visualizacao/execucao.py` (`ExecucaoReplay`) e a opção `replay`
em `__main__.py`, desviada antes de `build_spark`. O comando refaz a árvore oficial (`DadosModelo` + `Arvore.buscar`),
lê a validação inteira do Gold, prevê cada medição e grava `web/dados/replay.json` com `meta`, `fluxos`, `medicoes`
(`f`, `t`, `rtt`, `timeout`, `atual`, `previsto`, `futuro`, `conferivel`) e, por enquanto, uma rota reta: um ponto
provisório único para as sondas e um ponto por país de destino.

**Critérios de aceite:**
- [ ] `config.py` tem `BLOCO_REPLAY` (= validação; origem: spec, "Bloco exibido"), a pasta `WEB`, `ARQUIVO_REPLAY` e
      os pontos por país (BR, JP, SG, US, DE, PT), com a origem comentada
- [ ] Roda sem Java; sem o Gold, termina com "Rode antes: uv run python -m preditor gold"
- [ ] Checagens automáticas: nenhuma linha de `teste`; hiperparâmetros da árvore refeita = `arvore_oficial.json`;
      número de conferíveis = N da validação do `DadosModelo`; F1 macro e matriz recalculados do JSON (só
      conferíveis) = `metricas_validacao.csv` e `matriz_validacao.csv`; medições em ordem de `t`; todo `f` aponta
      para um fluxo; duas execuções geram o mesmo arquivo
- [ ] `web/dados/` no `.gitignore`

**Verificação:**
- [ ] `uv run python -m preditor replay` e `JAVA_HOME= uv run python -m preditor replay`
- [ ] `uv run python -m preditor arvore` continua passando
- [ ] `git status` não mostra `web/dados/replay.json`

**Dependências:** nenhuma
**Arquivos:** `src/preditor/config.py`, `src/preditor/visualizacao/__init__.py`,
`src/preditor/visualizacao/exportacao.py`, `src/preditor/visualizacao/execucao.py`, `src/preditor/__main__.py`,
`.gitignore`
**Escopo:** médio

## ✅ V2: Página mínima com pulsos

**Descrição:** Criar `web/` com o mapa-múndi em traço (D3 + TopoJSON em `web/vendor/`), o relógio do replay e os
pulsos em canvas: a cada medição, um pulso vai da sonda ao destino e volta, com duração proporcional ao RTT (piso e
teto) e cor do `status_atual`; em timeout, para no meio e some. Botão tocar / pausar. Estilo-base neo-brutalista
(fundo creme, bordas pretas, sombra dura, tipografia pesada) e o aviso fixo de rota ilustrativa.

**Critérios de aceite:**
- [ ] A página abre com um comando e funciona sem internet (nada de CDN)
- [ ] O relógio mostra a data e a hora reais da medição e os pulsos saem na ordem do JSON
- [ ] Pulso de timeout é visivelmente diferente do pulso que volta
- [ ] As três classes têm cor e rótulo de texto (nunca só cor); aviso de rota ilustrativa sempre visível

**Verificação:**
- [ ] Abrir a página, tocar, pausar, retomar; console sem erro
- [ ] Desligar a rede e recarregar: a página continua funcionando
- [ ] Baixar D3 / TopoJSON / contorno do mundo exige rede uma vez: se falhar, parar e avisar o dono

**Dependências:** V1
**Arquivos:** `web/index.html`, `web/estilo.css`, `web/app.js`, `web/mapa.js`, `web/vendor/*`
**Escopo:** médio

## Checkpoint A (revisão do dono)

- [ ] `replay` passa em todas as checagens
- [ ] Pulsos indo e voltando no mapa; estilo-base aprovado
- [ ] Dono decide se instala `frontend-ui-engineering`

---

## ✅ V3: Sondas, catálogo de cabos e rotas em trechos

**Descrição:** Criar `visualizacao/coletar_sondas.py` (script à parte: consulta a API pública do RIPE Atlas para as
13 sondas e grava `visualizacao/sondas.csv`) e `visualizacao/rotas.py`. O catálogo de cabos e os hubs terrestres
vão para `config.py`. Cada fluxo recebe uma rota em trechos `terrestre` / `submarino` com nós tipados (`sonda`,
`pop`, `aterragem`, `destino`), escolhida entre 1 a 3 opções por região com a semente 16 + `fluxo_id`. O exportador
soma os km (círculo máximo) e calcula o RTT mínimo teórico (2 × km / 200).

**Critérios de aceite:**
- [ ] `sondas.csv` versionado, com `prb_id`, latitude e longitude das 13 sondas; o `replay` continua offline
- [ ] Cada cabo do catálogo tem nome, estações de aterragem, pontos intermediários no mar e a fonte conferida
      (mapa da TeleGeography) no comentário; cabo não confirmado fica fora
- [ ] Checagens automáticas: toda rota começa na sonda e termina no destino; trechos encadeados; coordenadas
      válidas; trecho submarino usa cabo do catálogo e liga dois nós `aterragem`; destino fora do Brasil tem ao
      menos um trecho submarino e destino no Brasil, nenhum; `km` = soma dos trechos; `rtt_minimo_ms` = 2 × km / 200;
      mesma semente = mesmo JSON
- [ ] O comando imprime, por região, as rotas usadas, os km e o RTT mínimo ao lado da mediana real do baseline

**Verificação:**
- [ ] `uv run python -m preditor.visualizacao.coletar_sondas` (rede, uma vez) e depois `uv run python -m preditor replay`
- [ ] Se a API não devolver coordenada de alguma sonda: listar e perguntar ao dono
- [ ] Conferir à mão uma rota por região contra o mapa de cabos

**Dependências:** V2
**Arquivos:** `src/preditor/config.py`, `src/preditor/visualizacao/rotas.py`,
`src/preditor/visualizacao/coletar_sondas.py`, `src/preditor/visualizacao/sondas.csv`,
`src/preditor/visualizacao/exportacao.py`, `src/preditor/visualizacao/execucao.py`
**Escopo:** médio

## ✅ V4: Página desenha trechos terrestres e submarinos

**Descrição:** O mapa passa a desenhar a rota em trechos: terrestre em linha cheia, submarino em linha tracejada
com o nome do cabo; nós com forma por tipo (sonda, ponto de troca, aterragem, destino). O pulso percorre os trechos
em sequência, ida e volta. Legenda fixa; ao passar o mouse ou tocar em um trecho, aparecem tipo, nome e km. A
projeção é girada para nenhum trecho cruzar a borda.

**Critérios de aceite:**
- [ ] Terrestre e submarino distinguíveis sem depender de cor; nome do cabo legível
- [ ] Nenhuma rota é cortada pela borda do mapa
- [ ] Legenda com os 4 tipos de nó e os 2 tipos de trecho
- [ ] O pulso segue a linha desenhada, sem atalhos em linha reta

**Verificação:**
- [ ] Abrir a página e seguir um pulso por região de destino (Brasil, América do Norte, Europa, Ásia)
- [ ] Console sem erro

**Dependências:** V3
**Arquivos:** `web/mapa.js`, `web/app.js`, `web/estilo.css`, `web/index.html`
**Escopo:** médio

## Checkpoint B (revisão do dono)

- [ ] Rotas e cabos conferidos pelo dono; corte da projeção aprovado
- [ ] Números de km e RTT mínimo fazem sentido ao lado das medianas reais

---

## ✅ V5: Previsão, conferência e placar

**Descrição:** Quando o pulso volta, o fluxo ganha o selo "PREVISTO: <classe> em 12 min". Quando o relógio chega ao
instante do futuro, o selo vira "ACERTOU" ou "ERROU". Painel lateral com o placar acumulado da árvore e da
persistência (acertos / conferidas), a matriz 3×3 acumulada da árvore e o feed das últimas conferências. Medições não
conferíveis mostram "sem futuro para conferir" e ficam fora do placar. O exportador passa a gravar o instante do
futuro de cada medição conferível.

**Critérios de aceite:**
- [ ] Ao fim do replay, o placar e a matriz da página são iguais aos de `metricas_validacao.csv` e
      `matriz_validacao.csv` (árvore oficial e persistência)
- [ ] Pausar congela o placar; o placar só conta medições cujo futuro já passou no relógio
- [ ] Acerto e erro distinguíveis sem depender de cor

**Verificação:**
- [ ] Rodar o replay até o fim na maior velocidade e comparar os números com os CSVs
- [ ] `uv run python -m preditor replay`; console sem erro

**Dependências:** V2 (feita depois de V4, por mexer em `app.js`)
**Arquivos:** `web/app.js`, `web/index.html`, `web/estilo.css`, `src/preditor/visualizacao/exportacao.py`
**Escopo:** médio

## ✅ V6: Painel do fluxo e controles

**Descrição:** Clicar em um fluxo abre o cartão com as 8 colunas do X da última medição, a regra em português da
folha que decidiu, os km da rota e o RTT mínimo teórico ao lado da mediana real. Controles: velocidade (60×, 300×,
900×), barra de tempo para pular e filtro por região. O exportador passa a gravar `x`, `folha` e `regras`
(reutilizando `Regras.ler`).

**Critérios de aceite:**
- [ ] Checagens automáticas no exportador: toda `folha` do JSON tem regra; `x` tem as 8 colunas de `COLUNAS_ARVORE`
      e nenhuma proibida; valor ausente continua ausente (`null`)
- [ ] Pular no tempo recalcula o placar para aquele instante (o mesmo que tocar desde o início)
- [ ] O filtro por região esconde os fluxos, mas não muda o placar geral (ou a página diz que o placar é filtrado)

**Verificação:**
- [ ] Pular para o meio e para o fim: placar igual ao de tocar direto
- [ ] Clicar em um fluxo de cada região; conferir uma regra contra `regras_arvore_oficial.txt`

**Dependências:** V5
**Arquivos:** `web/app.js`, `web/index.html`, `web/estilo.css`, `src/preditor/visualizacao/exportacao.py`,
`src/preditor/visualizacao/execucao.py`
**Escopo:** médio

---

## ✅ V7: Acabamento visual e responsividade

**Descrição:** Fechar o neo-brutalismo descrito na spec (bordas de 3 a 4 px, sombras duras, cartões levemente
desalinhados, monoespaçada nos números), o contraste das cores das classes sobre o creme e o comportamento em janela
estreita e em projetor. Respeitar `prefers-reduced-motion` (replay começa pausado).

**Critérios de aceite:**
- [ ] Legível em 1280×720 (projetor) e em 375 px de largura, sem rolagem horizontal
- [ ] Texto com contraste suficiente sobre todas as cores de fundo
- [ ] Controles usáveis pelo teclado, com foco visível

**Verificação:**
- [ ] Conferir nos dois tamanhos e navegar pelos controles só com o teclado

**Dependências:** V6
**Arquivos:** `web/estilo.css`, `web/index.html`, `web/app.js`
**Escopo:** pequeno

## ✅ V8: Documentação e fechamento

**Descrição:** Atualizar `AGENTS.md` (estágio, comandos, convenções, decisões da visualização), o `README.md` e
`docs/README.md`; anotar os números de referência da execução nesta lista.

**Critérios de aceite:**
- [ ] `AGENTS.md` descreve o comando `replay`, a pasta `web/`, as checagens e as decisões (bloco exibido, rota
      simulada, sondas, cabos)
- [ ] O README diz como abrir a página

**Verificação:**
- [ ] Seguir o README do zero: `replay` e depois a página
- [ ] `git status`: nenhum dado de camada nem `web/dados/` versionado

**Dependências:** V7
**Arquivos:** `AGENTS.md`, `README.md`, `docs/README.md`, `tasks/todo-visualizacao.md`
**Escopo:** pequeno

## Checkpoint C (revisão do dono)

- [ ] Os 5 critérios de sucesso da spec
- [ ] Placar e matriz da página = CSVs da árvore
- [ ] Pronto para commit (só quando o dono pedir)

---

## Números de referência (execução de 02/10/2026)

- `replay.json`: 14.096 medições, 79 fluxos, 13.490 conferíveis, 606 sem futuro para conferir, 18 timeouts; 2,71 MB;
  sha256 `eec383559d4fad06…`.
- Placar ao fim do replay (= `metricas_validacao.csv`): árvore 11.183 / 13.490 (82,9 %), persistência 10.878 / 13.490
  (80,6 %); F1 macro 0,7457 e 0,7221.
- Matriz da árvore (linha = aconteceu, coluna = previsto; OK, RISCO, FALHA): `[[7485,270,390],[680,789,140],[569,258,2909]]`.
- Rotas: 13 sondas, 7 cabos, 0 fluxos com RTT mínimo teórico acima da mediana real.

## Pendências (decisão do dono)

- Checkpoint B fechado em 02/10/2026: o dono confirmou as rotas (sorteio só entre as fisicamente possíveis, destinos
  inferidos), manteve "Monet por Fortaleza" para todas as sondas e as colunas `pais` / `asn` de `sondas.csv` (é uma
  simulação).
- As últimas correções da V7 (comando `servir`, cartão do fluxo sem corte) foram conferidas à mão, sem nova revisão.
  Não foram refeitos o teste de 200 cargas simultâneas com o servidor novo nem a conferência dos selos a 900×.
- Sem teste em Firefox, Safari, leitor de tela ou toque real (só Chrome).
