# Tarefas: Piso na regra 3 do rótulo

Spec: `SPEC-piso-regra3.md`. Plano: `tasks/plan-piso-regra3.md`.
**Execução em lotes (decisão do dono, 09/10/2026):** o implementador faz **todas as tarefas de um lote em sequência,
sem parar entre elas**, e só para no checkpoint do fim do lote. A revisão (do agente principal, com o dono) acontece
só nos checkpoints. Lotes: **1 = P1 a P3**, **2 = P4 a P6**, **3 = P7 e P8**. Cada lote começa só depois do checkpoint
anterior ser aprovado.

**Paradas obrigatórias dentro de um lote** (parar na hora e relatar, sem seguir e sem afrouxar nada):
- uma checagem existente falha por causa do dado novo (inclusive `Regras.verificar` com `CASAS_LIMIAR_REGRA`);
- um resultado cai fora das faixas de risco do plano (ajustada com peso fora de 0,66 a 0,71 de F1; árvore da Tarefa 3
  fora de 20 a 40 folhas);
- o piso em `None` não reproduz o Gold de antes, ou o X mudou;
- seria preciso mudar algo fora da lista de arquivos da tarefa.

Nada é commitado sem o dono pedir. Não mexer em `notebooks/02_post_medicoes_periodicas.ipynb` (alteração antiga do dono).
O Gold precisa de Java 17: `JAVA_HOME=/opt/homebrew/opt/openjdk@17 uv run python -m preditor gold`.

## Fase 1: o rótulo

- [x] **P1: cópia de referência das saídas de hoje**
  - Descrição: antes de mexer em código, copiar `data/gold/` para `data/gold_antes_do_piso/`, `data/modelo/` para
    `data/modelo_antes_do_piso/` e `web/dados/replay.json` para `data/replay_antes_do_piso.json` (tudo ignorado pelo
    git). Anotar as contagens por regra do Gold de hoje (16.305 na regra 3 etc.).
  - Aceite: as cópias existem, `diff -r` com os originais não mostra diferença, e `git status` não mostra arquivo novo.
  - Verificação: `diff -r data/gold data/gold_antes_do_piso && diff -r data/modelo data/modelo_antes_do_piso`;
    `git status --short`.
  - Depende de: nada. Arquivos: nenhum do repositório. Tamanho: XS.
  - Resultado (10/10/2026, conferido de novo): as três cópias são idênticas aos originais (`diff -rq` e `cmp` sem
    diferença); `git status` só mostra o que já existia antes (`.claude/agents/implementer.md`, o notebook 02 e os três
    arquivos de piso). Contagens por regra do Gold de antes (`data/gold_antes_do_piso/dataset_rotulado_B.parquet`,
    70.616 linhas): regra 1 = 1.381; regra 2 = 10; regra 3 = 16.305; regra 4 = 597; regra 5 = 9.501; regra 6 = 42.822.
    Destino previsto das rebaixadas (simulado sobre esse Gold, a cadeia das regras 4 a 6 sem a 3): regra 6 = 11.436;
    regra 5 = 2.929; regra 4 = 5; 1.935 ficam na regra 3; 9.251 das 14.370 têm z ≥ 8.

- [x] **P2: linha 3 com piso e as checagens do Gold**
  - Descrição: `PISO_AUMENTO_FALHA_PCT = AUMENTO_RISCO_PCT` em `config.py` (comentário: origem, decisão de 09/10/2026,
    `None` = RFC ao pé da letra); a linha 3 de `Rotulo._regra` ganha `aumento_pct >= piso` quando o piso não é
    `None`; em `__main__.py`, a `ok_com_z_extremo` é trocada por "nenhuma linha OK com z ≥ `Z_FALHA` e aumento ≥ piso"
    e entram as checagens 2, 3 e 4 da spec (regra 3 ⇒ piso; z e aumento altos ⇒ regra 1, 2 ou 3; z alto e aumento
    abaixo do piso ⇒ nunca a regra 3; impressão de quantas a regra 3 perdeu e para onde foram).
  - Aceite:
    - com o piso em `None`, o Gold sai **idêntico** ao de P1 (`dataset_rotulado_B.parquet`, `features_B.parquet`,
      `contagem_classes.csv`): o refatoramento não mexeu em mais nada;
    - com o piso em 30, `features_B.parquet` é idêntico ao de P1 coluna a coluna; só mudam `regra`, `status_atual` e
      `status_futuro`;
    - nenhuma linha com `aumento_pct` < 30 está na regra 3; as 14.370 rebaixadas aparecem (11.436 OK, 2.929 RISCO,
      5 regra 4; valores de referência, não constantes), as checagens antigas continuam passando, e cada bloco tem
      as 3 classes;
    - as 3 linhas de exemplo impressas continuam sendo encontradas (a FALHA da regra 3 usa z ≥ 5).
  - Verificação: `gold` duas vezes (piso `None`, depois 30), com `diff` do parquet na primeira e comparação de
    `features_B` na segunda (pandas, `DataFrame.equals` ou `assert_frame_equal`).
  - Depende de: P1. Arquivos: `config.py`, `gold/calculo_y/rotulo.py`, `__main__.py`. Tamanho: M.
  - Resultado (10/10/2026), por execução de `gold` (log na pasta de rascunho, não no repositório):
    - **Vermelho** (piso 30, regra antiga, checagens novas): a checagem 2 parou com "14370 linhas da regra 3 sem
      z_robusto >= 3.5 e aumento_pct >= 30", como esperado.
    - **Piso `None`** (reversão): sai `exit 0`; `features_B`, `baseline_por_fluxo` e `dataset_rotulado_B` (inteiro)
      idênticos a `data/gold_antes_do_piso/`, por conteúdo e exato; `contagem_classes.csv` e
      `limites_por_regiao.csv` idênticos em bytes.
    - **Piso 30** (código final; rodado duas vezes, mesmo conteúdo nas duas): sai `exit 0`; `features_B` e
      `baseline_por_fluxo` idênticos; `dataset_rotulado_B` idêntico em tudo menos `regra`, `status_atual` e
      `status_futuro` (`bloco` igual). `contagem_classes.csv` muda, como esperado.
    - Contagem por regra, antes → depois: regra 1 = 1.381 → 1.381; regra 2 = 10 → 10; **regra 3 = 16.305 → 1.935**;
      regra 4 = 597 → 602; regra 5 = 9.501 → 12.430; regra 6 = 42.822 → 54.258. Total 70.616 nos dois.
    - Destino impresso pelo Gold: 14.370 saíram da regra 3 (regra 4 = 5; regra 5 = 2.929; regra 6 = 11.436), igual à
      simulação. Checagens 1 a 3 passam; nenhuma linha com aumento < 30 % na regra 3. Os 3 exemplos continuam sendo
      encontrados (a FALHA usa 1.849 linhas da regra 3 com z ≥ 5). Os 3 blocos têm as 3 classes.
    - Desvio: a verificação de "diff do parquet" foi trocada por comparação de conteúdo (pandas, exata, ordenada por
      `fluxo_id`, `t`), porque o Spark põe UUID no nome das partes e a ordem de linhas pode variar; o `diff` daria
      diferença falsa.

- [x] **P3: `arvore` e `ajuste` com o rótulo novo**
  - Descrição: sem mudar código, rodar `arvore` e `ajuste` e conferir que todas as checagens passam. Se alguma falhar por
    causa do dado novo, parar e avisar o dono (não afrouxar checagem).
  - Aceite:
    - ambos terminam com todas as checagens;
    - os números reais (persistência, Tarefa 3, ajustada sem e com peso: folhas, F1, ganho, recall, acerto em OK →
      FALHA) são anotados ao lado dos de `data/modelo_antes_do_piso/`, e o F1 não é comparado entre rótulos;
    - o teste continua fechado (nenhuma linha dele medida).
  - Verificação: `uv run python -m preditor arvore && uv run python -m preditor ajuste`.
  - Depende de: P2. Arquivos: nenhum (talvez `config.py` se `CASAS_LIMIAR_REGRA` precisar subir, só com o dono avisado).
    Tamanho: S.
  - Resultado (10/10/2026): `arvore` e `ajuste` terminaram com `exit 0` e todas as checagens, sem nenhuma checagem
    afrouxada e sem mudar código. `Regras.verificar` passou com 4 casas (`CASAS_LIMIAR_REGRA` não precisou subir).
    Faixas do plano: árvore da Tarefa 3 com 29 folhas (dentro de 20 a 40); ajustada com peso com F1 0,6851 (dentro de
    0,66 a 0,71). O teste continua fechado (só o N aparece). Antes × depois, nas mesmas linhas de validação
    (N = 13.490), CSVs de `data/modelo_antes_do_piso/` × `data/modelo/`. O F1 não se compara entre rótulos; o que se
    compara é o ganho sobre a persistência:

    | Modelo | Antes: folhas, F1, ganho, recall FALHA, OK → FALHA | Depois: folhas, F1, ganho, recall FALHA, OK → FALHA |
    |---|---|---|
    | persistência | F1 0,7221; recall FALHA 0,809 | F1 0,6355; recall FALHA 0,498 |
    | árvore da Tarefa 3 (oficial, Gini, profundidade/folha mínima 4/50 → 5/50) | 16 folhas; 0,7457; +0,0236; 0,779; 1,8 % | 29 folhas; 0,6863; +0,0508; 0,478; 18,4 % |
    | ajustada sem peso | Gini 2/500, 4 folhas; 0,7553; +0,0332; 0,722; 0,2 % | Gini 5/50, 29 folhas; 0,6820; +0,0464; 0,480; 18,4 % |
    | ajustada com peso {1; 2; 1,5} | Gini 4/100, 16 folhas; 0,7600; +0,0379; 0,754; 0,6 % | entropia 6/100, 40 folhas; 0,6851; +0,0496; 0,505; 16,4 % |

    - Recall de RISCO da ajustada com peso: 0,564 → 0,532.
    - Os parâmetros escolhidos pela regra da Tarefa 4 mudaram (a ajustada com peso passou de Gini para entropia); isso é
      resultado da regra, não ajuste manual.
    - Não há confirmação de que o ganho sobre a persistência ficou maior: as diferenças de ganho são pequenas e
      precisam do IC e da dobra interna do P7 (ressalva da spec).

### Checkpoint 1: fim do lote 1 (P1 a P3). O implementador para aqui.

- [x] `gold`, `arvore` e `ajuste` passam em todas as checagens, nenhuma afrouxada
- [x] Números reais anotados (tamanho das árvores, ganho sobre a persistência, OK → FALHA)
- [x] Relatório do implementador com: comandos rodados, saídas-chave, desvios do plano
- [ ] Revisão do agente principal e do dono antes do lote 2

## Fase 2: peso e página

- [x] **P4: varredura de pesos no rótulo novo (análise)**
  - Descrição: no scratchpad, repetir a varredura (30 combinações de peso de RISCO e FALHA, mais `balanced`, grade
    inteira de 56, regra de escolha da Tarefa 4, F1 da validação e da dobra interna) com o Gold novo.
  - Aceite: tabela dos pesos; decisão registrada. Só se alguma combinação ganhar mais de 0,005 de F1 macro na validação
    **e** na dobra interna sobre {1; 2; 1,5}, troca `PESO_CLASSES_AJUSTE` e refaz `ajuste`; senão, mantém.
  - Verificação: tabela impressa; se houver troca, `uv run python -m preditor ajuste` passa.
  - Depende de: P3. Arquivos: nenhum (ou `config.py`, se trocar). Tamanho: S.
  - Resultado (10/10/2026): **nenhuma combinação passa nas duas medidas; o peso fica {OK 1; RISCO 2; FALHA 1,5}** e
    `ajuste` não foi refeito. Análise fora do repositório: `data/analise_piso_regra3/varredura_pesos.py`, `.csv` e
      `.log` (pasta em `data/`, ignorada pelo git; a mesma cópia está no scratchpad da sessão).
    - Conferência antes da varredura: a busca de {1; 2; 1,5} e a sem peso, refeita pelo código do projeto, bate com
      `busca_ajuste.csv` nas 112 linhas (F1 com diferença máxima de 4,8e-7) e nas escolhidas: entropia 6/100, 40
      folhas, F1 0,685091; Gini 5/50, 29 folhas, F1 0,681971.
    - Grade: a grade de 30 pesos da tarefa não estava salva em lugar nenhum, então foi definida agora: RISCO {1; 1,5;
      2; 2,5; 3} × FALHA {1; 1,5; 2; 2,5; 3; 4}, com OK = 1, mais `sem peso` e `balanced` (32 linhas).
    - Dobra interna: 60 % iniciais do treino, por tempo (corte em 2026-09-23T07:58:52), com folga de 3 medições por
      fluxo no corte; sub-treino 20.560 linhas, dobra 13.864. Em cada split, a grade inteira e a regra de escolha da
      Tarefa 4 escolhem a árvore e o F1 é medido no mesmo split.
    - Critério: ganho acima de 0,005 sobre {1; 2; 1,5} nas duas medidas. Pelo critério, nenhuma passa. Mais próximas:
      RISCO 2,5 / FALHA 2 (+0,0079 na validação, −0,0036 na dobra); RISCO 1 / FALHA 2,5 (−0,0067 na validação,
      +0,0079 na dobra); RISCO 1,5 / FALHA 1,5 (+0,0053 na validação, +0,0016 na dobra).
    - Atual {1; 2; 1,5}: validação 0,6851 (40 folhas), dobra interna 0,6857. Faixas do plano: dentro de 0,66 a 0,71.

- [x] **P5: `replay` com os dados novos**
  - Descrição: rodar `replay` depois de P3/P4 e conferir as checagens (árvore refeita = JSON, matriz e F1 do JSON = CSVs,
    regras das folhas, etc.). Investigar qualquer falha por dado novo (inclusive um valor fixo de 16 folhas / 31 nós).
  - Aceite: `replay` termina com todas as checagens; o `replay.json` novo traz as árvores com os nós novos.
  - Verificação: `uv run python -m preditor replay`; `grep -rn "31\|16 folhas" src/preditor/visualizacao`.
  - Depende de: P3 (e P4, se mudou o peso). Arquivos: nenhum previsto. Tamanho: S.
  - Resultado (10/10/2026): `uv run python -m preditor replay` terminou com `exit 0` na primeira execução, sem parada
    e sem mudar código. Como P4 manteve o peso, o replay é o final.
    - Checagens: árvore oficial refeita = `arvore_oficial.json` (29 folhas); ajustada refeita = `arvore_ajustada.json`
      (`ajustada_com_peso`, entropia 6/100, 40 folhas); percurso no JSON = folha gravada nas 14.096 medições; `x` com as 8
      colunas, nenhuma proibida; `CASAS_X_REPLAY` (4) e `CASAS_LIMIAR_REGRA` (4) passaram; teste fora do JSON; conferíveis
      = 13.490 = N da validação; F1 do JSON = CSV (oficial 0,6863; ajustada 0,6851); matriz = `matriz_validacao.csv`.
    - Árvores exportadas: oficial 57 nós (= `tree_`), 29 folhas; ajustada 79 nós (= `tree_`), 40 folhas.
    - `replay.json`: 3.747.707 bytes (antes do piso: 3.753.049 em `data/replay_antes_do_piso.json`).
    - `grep -rn "31\|16 folhas" src/preditor/visualizacao`: nenhum número fixo de nós ou folhas.

- [x] **P6: painel da árvore para 29 e 40 folhas**
  - Descrição: em `web/arvore.js` (e `web/estilo.css`, `web/index.html` se preciso): largura do SVG = máx(1280,
    folhas × 80) dentro de um contêiner com rolagem horizontal; ao acender o caminho do fluxo em foco, rolar para
    deixá-lo na tela; atualizar `aria-label` e comentários que dizem 16 folhas / 31 nós. Só `textContent` e
    `createElementNS`, como hoje; sem `innerHTML`.
  - Aceite:
    - as duas árvores aparecem inteiras e legíveis (rolando), sem nó cortado nem sobreposto;
    - com um fluxo em foco, o caminho aceso fica à vista nas duas árvores, trocando pelo seletor;
    - mapa, cartão e placar não mudam; ao fim do replay o placar e a matriz são iguais aos CSVs;
    - console sem erro; CSP `default-src 'self'` intacta.
  - Verificação: `servir` pelo navegador embutido (preview), com fluxos de cantos diferentes, em largura de notebook e
    de tela grande; `read_console_messages`; captura de tela. `tempo.js`, `placar.js` e `caminho.js` não mudam (rodam em Node).
  - Depende de: P5. Arquivos: `web/arvore.js`, `web/estilo.css`, `web/index.html`, `SPEC-arvore-na-pagina.md`.
    Tamanho: M.
  - Resultado (10/10/2026): `web/arvore.js`, `web/estilo.css`, `web/index.html` e `SPEC-arvore-na-pagina.md` mudaram;
    `web/tempo.js`, `web/placar.js`, `web/caminho.js` e `web/app.js` não mudaram. Sem `innerHTML` e sem `style` inline (só
    atributos `width`, `height`, `viewBox`).
    - Largura: SVG com `width` e `height` iguais ao viewBox, `max(1280, 80 × folhas)`: 2320 × 380 (oficial, 29 folhas) e
      3200 × 442 (ajustada, 40 folhas). 1 unidade = 1 px; o CSS deixou de encolher (`width: 100%` saiu).
    - Rolagem: contêiner `.arv-rolagem` (rolagem horizontal, `tabindex="0"`, `role="region"`). Ao acender o caminho,
      rola-se o contêiner para a folha em foco, só se ela está fora do trecho visível. Não usa `scrollIntoView`.
    - Chrome real, `servir` em 127.0.0.1:8000, telas 1366 × 768 e 1920 × 1080, seis casos (canto esquerdo, centro e
      direito em cada árvore): **12 de 12 conferências passaram** (folha e previsão iguais ao JSON; caminho aceso com
      todos os passos; folha na tela; nenhuma sobreposição de caixas nem texto fora da caixa; sem `style` no SVG; sem
      rolagem horizontal da página). Console sem erro nem aviso.
    - Verificação pelo navegador embutido (preview), nas seis trocas de fluxo, medição e árvore: mesmos resultados.
    - Telas estreitas, 768 × 1024 e 375 × 812 (painel abaixo do mapa): 12 de 12 conferências passam, sem rolagem
      horizontal da página em nenhuma das duas; console sem erro. Não foi preciso mexer em CSS.
    - Fim do replay (barra no último instante): placar da árvore 11.594 / 13.490 (85,9 %); persistência 11.018 / 13.490.
      Matriz da oficial: OK 10.297 / 405 / 69; RISCO 1.081 / 1.014 / 32; FALHA 224 / 85 / 283 = as linhas
      `arvore_oficial` de `matriz_validacao.csv`. Conferíveis 13.490.
    - Capturas: `tasks/capturas-piso/` (oficial e ajustada, cantos esquerdo e direito, em 1366 e 1920): ver o relatório.
    - Rolagem da janela: só a seleção de fluxo rola a janela na vertical (51 px, medido), pelo `scrollIntoView` do cartão
      que já estava em `app.js` (linha 523). Seletor de árvore e barra não rolam a janela.

### Checkpoint 2: fim do lote 2 (P4 a P6). O implementador para aqui.

- [x] `replay` passa e a página confere (placar e matriz = CSVs)
- [x] As duas árvores legíveis no painel
- [x] Capturas de tela das duas árvores no painel, no relatório do implementador (`tasks/capturas-piso/`, 10/10/2026)
- [ ] Revisão do agente principal e do dono antes do lote 3

## Fase 3: documentação

- [x] **P7: relatório (seção 8) e análise de robustez**
  - Descrição: no scratchpad, medir no Gold real o IC 95 % por fluxo do ganho sobre a persistência e o ganho na
    dobra interna (60 % / 40 % do treino) das árvores escolhidas, antes × depois. Escrever a seção 8 de
    `docs/relatorio_analise_arvore.md`: tabela antes × depois (com os números de `data/modelo_antes_do_piso/`), a
    tabela de destino das rebaixadas, as ressalvas medidas e a explicação de onde vem o 30. Nota no topo: as seções 1 a
    7 valem para o rótulo anterior (commit `055c422`). As seções 1 a 7 não são reescritas.
  - Aceite: cada número da seção 8 vem de uma execução (`data/modelo/` ou script do scratchpad), e as ressalvas
    (ganho sem prova de ser maior, queda do recall de FALHA, árvore maior, F1 incomparável) estão ditas.
  - Verificação: conferir os números do texto contra `data/modelo/*.csv` e a saída da análise.
  - Depende de: P6. Arquivos: `docs/relatorio_analise_arvore.md`, `docs/README.md`. Tamanho: M.
  - Resultado (10/10/2026):
    - `docs/relatorio_analise_arvore.md`: nota no topo (as seções 1 a 7 valem para o rótulo anterior, sem reescrita) e a
      seção 8 (8.1 a 8.7): o que muda no rótulo, de onde vem o 30, antes × depois na validação, ganho com IC 95 % por
      fluxo e dobra interna, ressalvas medidas, peso e decisões do dono, leitura.
    - Análise: `data/analise_piso_regra3/robustez_piso.py` (log ao lado, ~3 min) grava `numeros_secao8.csv` (268 linhas,
      com a fonte de cada número), `ic_ganho.csv`, `ic_pareado.csv`, `modelos_validacao_e_dobra.csv`,
      `contagem_regras.csv`, `destino_rebaixadas.csv` e `classes_no_modelo.csv`. `conferir_secao8.py`: 420 números na
      seção 8, todos com fonte (arquivo, log, varredura ou constante com o motivo ao lado).
    - Conferências do script (todas passaram): X idêntico nos dois Golds, pela chave (24 colunas) e em `features_B`;
      árvores refeitas = CSVs de `modelo_antes_do_piso/` e `modelo/` (F1 com 6 casas, matrizes, folhas, parâmetros);
      dobra da ajustada com peso, depois = 0,685727 (P4); corte da dobra igual nas duas versões (2026-09-23T07:58:52;
      sub-treino 20.560, dobra 13.864, folga 237). IC da oficial antes, na validação: [+0,0107; +0,0330], que bate com a
      seção 2 ([+0,011; +0,033]).
    - Rótulo com piso: `conferir_rotulo_piso.py` (Spark, em memória, sem gravar): piso `None` = Gold de antes em 70.616
      linhas; piso 30 = Gold atual; as checagens do `__main__` passam nas duas.
    - **Conflito medido:** a persistência da dobra antes é 0,7145 (divisão do P4), e não 0,7141 da seção 3. A divisão da
      seção 3 veio de um script anterior, que não ficou salvo. `variantes_dobra_antes.py` não reproduz 0,7141 (pelas
      linhas do treino inteiro dá 0,7134). Anotado na seção 8.5 (item 7); a seção 3 não foi reescrita.
    - Achados que não estavam no protótipo (estão no texto): a precisão de FALHA cai (ajustada com peso 0,910 → 0,643);
      a vantagem da ajustada com peso sobre a oficial some (+0,0144 → -0,0012 na validação); na dobra, o ganho da
      ajustada com peso cai (+0,0391 → +0,0346).
    - Não feito, de propósito: sensibilidade a outros valores de piso. Não foi medida no Gold final, e a seção 8.2 diz isso.
      O teste continua fechado: nada foi medido nele.

- [x] **P8: AGENTS.md, specs, READMEs e memória**
  - Descrição: atualizar o que a lista "Documentos que ficam desatualizados" da spec aponta: `AGENTS.md` (estágio,
    decisões, comandos e checagens, "arvore e replay idênticos"), decisão 5 de `SPEC-calculo-y.md`, notas em
    `SPEC-ajuste-arvore.md`, README dos dados do Gold se descrever a regra 3, e a memória do projeto (pendência da
    professora resolvida). Não editar a RFC nem os diários das tarefas.
  - Aceite: nenhum número do rótulo antigo aparece como atual; os 7 critérios de sucesso da spec marcados.
  - Verificação: `grep -rn "0,7457\|0,779\|88 %\|16 folhas\|31 nós\|sem piso" AGENTS.md SPEC-*.md docs README.md data/README.md`
    e conferir uma a uma que as ocorrências restantes dizem "rótulo anterior".
  - Depende de: P7. Arquivos: `AGENTS.md`, `SPEC-calculo-y.md`, `SPEC-ajuste-arvore.md`, `data/README.md` (se couber).
    Tamanho: M.
  - Resultado (10/10/2026):
    - Atualizados: `AGENTS.md` (estágio, comandos da análise, checagens do piso, "arvore e replay idênticos com o mesmo
      Gold", contagens de nós como resultado e não invariante, decisões do piso, do peso, de recall e precisão e do teto
      marcadas como rótulo anterior, painel, fluxo de trabalho); `SPEC-calculo-y.md` (decisão 5); `SPEC-ajuste-arvore.md`
      (nota no topo, respostas às pendências 1 e 2, teto marcado); `SPEC-piso-regra3.md` (estado dos sete critérios, sem
      reescrever nenhum); `docs/README.md` (entrada do relatório); `README.md` da raiz (fora da lista: "31 nós" trocado
      por "todos os nós"); memória do projeto (`professora-liberou-pesos-e-piso.md` como resolvido e aplicado, sem
      duplicata; o índice `MEMORY.md` acompanha).
    - `data/README.md` não descreve a regra 3: sem mudança.
    - Grep de verificação (números do rótulo antigo, sobre AGENTS, SPEC-*.md, docs/README, README, data/README e o
      relatório): as ocorrências restantes dizem "rótulo anterior", ou são texto histórico (protótipo, prévia de antes da
      remoção das duplicatas, a lista de documentos desatualizados da própria spec). Revisadas uma a uma.
    - Não editados, por regra: a RFC; os diários das tarefas (inclusive `Tarefa4_Ajuste_da_Arvore.md`); os
      `tasks/todo-*.md` com números de referência; `notebooks/02`; `.claude/agents/implementer.md`; `.gitignore`.

### Checkpoint final: fim do lote 3 (P7 e P8)

- [x] Critérios de sucesso 1 a 7 da spec marcados (estado e evidência em `SPEC-piso-regra3.md`; no 7, a parte do diário da Tarefa 4 é do dono)
- [x] Piso em `None` ainda reproduz o Gold de antes (reconferido em 10/10/2026 com `conferir_rotulo_piso.py`, em memória, sem gravar: 70.616 linhas iguais)
- [ ] O dono leva ao diário da Tarefa 4 (seção 4) o registro da conversa com a professora
- [ ] Revisão do dono; commit só se ele pedir
