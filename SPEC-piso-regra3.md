# Spec: Piso na regra 3 do rótulo (revisão do Y)

Status: **aprovada pelo dono em 09/10/2026**, que delegou ao agente as quatro perguntas abertas (decididas abaixo, em
"Decisões fechadas"; o dono pode revê-las a qualquer momento).

## Objetivo

Dar um piso à regra 3 do rótulo (RFC §8.4): hoje `z_robusto` ≥ 3,5 basta para a medição ser FALHA. Passa a exigir
também `aumento_pct` ≥ 30 %. A professora liberou, em conversa com o dono, configurar pesos de classe e dar piso às
regras (relato do dono, 09/10/2026). Isto fecha as duas pendências do relatório (`docs/relatorio_analise_arvore.md`,
seção 7.3): o peso de classe e a limitação conhecida da regra 3.

**Por que o piso.** Das 16.305 FALHAs da regra 3, 88 % têm `aumento_pct` < 30 %: são fluxos muito estáveis, em que um
MAD de décimos de ms faz uma variação de 1 ms virar z ≥ 3,5. 68 % dos episódios de FALHA duram uma medição, e nenhum
modelo (nem um boosting de 300 árvores) antecipa o início de uma falha com esse alvo: acerto em OK → FALHA de 0,6 % na
árvore ajustada. Com o piso, os picos de milissegundos saem do alvo e a árvore passa a acertar cerca de 20 % dos
inícios de FALHA (protótipo, ver "Referência do protótipo").

**De onde vem o 30.** É o limite de RISCO que a tabela da RFC já usa (`AUMENTO_RISCO_PCT` = 30, "30 ≤ `aumento_pct`
≤ 80", linha 5). A coerência é interna à tabela: uma FALHA não pode ser menos severa que o limite de RISCO. O valor
**não foi escolhido varrendo pisos na validação**: o protótipo mediu 10, 20, 30 e 50 só para mostrar que o resultado
não depende de um número exato, e os vizinhos dão resultados parecidos.

### O que muda e o que não muda

Muda: **só a linha 3 do Y**, e tudo o que depende do Y (`status_atual`, `status_futuro`, a árvore e os números).

Não muda:

- O X inteiro: nenhuma coluna de `features_B` é recalculada, inclusive `moderado` e `n5_moderado`. Conferido por
  comparação com o arquivo anterior (critério de sucesso 2).
- As linhas 1, 2, 4, 5 e 6 da tabela, os limiares delas, o baseline, o corte A/B, o recorte dos blocos, a folga, a
  semente 16, o `fit` só no treino, a regra de escolha da ajustada (tolerância 0,005) e a grade.
- O teste continua fechado até a Tarefa 5. O piso muda o rótulo das linhas do teste no Gold, mas nada delas é medido.
- A RFC (`docs/projeto_preditor_redes/`) não é editada: é o texto da professora. O desvio fica registrado aqui, no
  `SPEC-calculo-y.md` e no `AGENTS.md`.

### A regra nova

| `regra` | Classe | Condição (nova) |
|---|---|---|
| 1, 2 | FALHA | iguais |
| 3 | FALHA | `z_robusto` ≥ 3,5 **e** `aumento_pct` ≥ `PISO_AUMENTO_FALHA_PCT` (30) |
| 4, 5, 6 | | iguais |

A medição com z ≥ 3,5 e `aumento_pct` < 30 % **não dispara a regra 3** e segue a tabela: vai à linha 4, 5 ou 6. O
`moderado` do X não é alterado, então ela só é "moderada" se `jitter_relativo` ≥ 3 (a faixa de z do `moderado` termina
em 3,5).

**Para onde vão as medições rebaixadas** (Gold atual, 3 blocos juntos): 14.370 das 16.305 da regra 3 (88,1 %); 1.935
continuam na regra 3.

| Destino | Medições | Classe |
|---|---|---|
| Regra 6 | 11.436 | OK |
| Regra 5 | 2.929 | RISCO |
| Regra 4 | 5 | FALHA |

### Consequência que o dono precisa aprovar sabendo

Das 14.370 rebaixadas, 9.251 têm z ≥ 8 (mediana de z = 14,65; mediana de `aumento_pct` = 4,2 %). Ou seja, **uma
medição com z = 14 e aumento de 4 % passa a ser OK, enquanto z = 2,5 (com aumento pequeno) ainda conta como desvio
moderado para a janela de RISCO.** É coerente com o objetivo do piso (esses z gigantes vêm de MAD de décimos de ms:
no fluxo `7242|150.164.1.222|28095697`, mediana 55,3 ms e MAD 0,19 ms, z = 3,5 equivale a ~1 ms), mas é uma ordem
estranha à primeira vista e deve aparecer assim na explicação à professora.

**Alternativa medida e descartada:** tratar a rebaixada como "moderada" (`moderado` = 1, recalculando `n5_moderado`).
O RISCO sobe de 17,7 % para 31,5 % das linhas, o que contradiz a RFC ("RISCO é raro", RFC seção 10) e mexe numa coluna do
X, com ganho sobre a persistência igual (+0,043 a +0,045). Fica fora.

### Referência do protótipo (pandas, validação; não são constantes)

O protótipo reproduz o `status_atual` e o `status_futuro` do Gold atual linha a linha antes de aplicar o piso. Os
números mudam um pouco no Gold em Spark. **O F1 não se compara entre rótulos** (0,76 → 0,68 não é piora: a
persistência também cai, de 0,722 para 0,636); o que se compara é o ganho sobre a persistência e o acerto nos inícios
de FALHA.

| Validação | Sem piso (hoje) | Com piso 30 % |
|---|---|---|
| FALHA / RISCO nas linhas de treino + validação | 23,8 % / 13,8 % | 5,4 % / 17,7 % |
| Persistência, F1 macro | 0,7221 | 0,6355 |
| Árvore da Tarefa 3 (8 colunas, sem peso, Gini 4/50 → 5/50) | 16 folhas, 31 nós, 0,7457 (+0,0236) | **29 folhas, 57 nós**, 0,6863 (+0,0508) |
| Ajustada sem peso (grade completa, 56) | Gini 2/500, 4 folhas, 0,7553 (+0,0332) | Gini 5/50, 29 folhas, 0,6820 (+0,0464) |
| Ajustada com peso {1; 2; 1,5} (grade completa, 56) | Gini 4/100, 16 folhas, 0,7600 (+0,0379) | entropia 6/100, **40 folhas**, 0,6851 (+0,0496) |
| Acerto em OK → FALHA (ajustada) | 0,6 % | 16 a 18 % |
| Recall de FALHA / RISCO (ajustada com peso) | 0,754 / 0,564 | 0,505 / 0,532 |

Ressalvas medidas, que vão para o relatório:

- **O ganho sobre a persistência não ficou comprovadamente maior.** Em um protótipo só com Gini (28 árvores), o IC
  95 % por fluxo do ganho foi [+0,018, +0,060] com o piso, contra [+0,027, +0,049] sem ele; na dobra interna (60 % /
  40 % do treino) o ganho foi +0,026 com o piso, contra +0,034 sem ele. O que melhora com clareza é o acerto em OK →
  FALHA (cerca de 200 casos na validação, então com ruído).
- **O recall de FALHA cai** (de 0,75 para 0,50): sobraram menos FALHAs, e as que sobram são os episódios reais, mais
  difíceis de antecipar a 12 min.
- **A árvore cresce.** A regra de escolha da Tarefa 3 (maior F1 puro) e a da Tarefa 4 (tolerância 0,005) ficam como
  estão e escolhem 29 e 40 folhas. A página foi desenhada para 16 folhas (ver "Impacto na página").

## Suposições (corrija agora ou sigo com elas)

1. O piso é só na regra 3. As regras 1 e 2 (perda, timeout) e 4 (aumento > 80 % repetido) ficam como estão.
2. A medição rebaixada segue a tabela como ela está (linha 4, 5 ou 6), sem tratamento especial e sem mexer no X.
3. O comportamento antigo precisa ser recuperável com uma linha em `config.py` (`PISO_AUMENTO_FALHA_PCT = None`).
4. A regra de escolha da Tarefa 3 e da Tarefa 4 **não** é ajustada para segurar o tamanho da árvore; o tamanho é
   reportado (e ver Perguntas abertas).
5. O peso {OK 1, RISCO 2, FALHA 1,5} é reavaliado no rótulo novo por uma varredura de análise (fora do repositório),
   e só muda se outra combinação ganhar por mais de 0,005 de F1 macro tanto na validação quanto na dobra interna.
6. As saídas de antes do piso são preservadas fora do git para a comparação (copia de `data/gold` e `data/modelo`).

## Impacto nos módulos

| Módulo | O que acontece |
|---|---|
| `config.py` | `PISO_AUMENTO_FALHA_PCT = AUMENTO_RISCO_PCT`, com o comentário de origem; `None` = regra 3 da RFC ao pé da letra |
| `gold/calculo_y/rotulo.py` | a linha 3 de `_regra()` ganha `aumento_pct >= piso` (só quando o piso não é `None`) |
| `__main__.py` (checagens do Gold) | ver "Checagens" abaixo |
| `modelo/` (`arvore`, `ajuste`) | **nenhuma mudança de código**; os resultados mudam porque o alvo mudou. `CASAS_LIMIAR_REGRA = 4` pode falhar em `Regras.verificar` numa árvore nova (aconteceu com a ajustada): se falhar, é o caso de subir as casas, com o dono avisado |
| `visualizacao/` | nenhuma mudança prevista; as checagens do `replay` leem os CSVs da árvore. Qualquer falha por dado novo é investigada uma a uma |
| `web/arvore.js` | **muda** (ver abaixo) |
| Docs | ver "Documentos que ficam desatualizados" |

### Impacto na página

O painel da árvore foi feito para 31 nós e 16 folhas (`LARGURA = 1280`, "16 folhas a 80 de distância", comentário de
`web/arvore.js`; `SPEC-arvore-na-pagina.md`: "legíveis a 1280 px sem rolagem"). Com 29 folhas na oficial e 40 na
ajustada, o desenho precisa de largura proporcional às folhas (80 por folha) e rolagem horizontal do cartão, mantendo
o caminho do fluxo em foco visível (rolar até o nó destacado). É a única mudança de código fora do Gold. Os números
31 e 16 nas specs e comentários passam a ser os da árvore escolhida.

## Checagens (a verificação do projeto é o pipeline rodar)

No Gold (`__main__.py`, hoje `_verificar_status_atual`):

1. **Reescrever** `ok_com_z_extremo` (hoje: nenhuma linha OK com z ≥ 3,5). Passa a ser: nenhuma linha OK com
   z ≥ `Z_FALHA` **e** `aumento_pct` ≥ piso. Sem essa troca, o Gold passa a falhar de propósito.
2. **Nova:** toda linha da regra 3 tem `aumento_pct` ≥ piso (e z ≥ `Z_FALHA`).
3. **Nova, por outro caminho:** toda linha com z ≥ `Z_FALHA` e `aumento_pct` ≥ piso está na regra 1, 2 ou 3 (nunca em
   4, 5 ou 6); e as com z ≥ `Z_FALHA` e `aumento_pct` < piso nunca estão na regra 3.
4. **Nova, impressão:** quantas linhas a regra 3 perdeu para o piso e para onde foram (regra 4 / 5 / 6), para o dono ver
   a tabela acima reproduzida no Gold real.
5. Continuam valendo todas as demais: regra ↔ classe, FALHA com precedência, `status_futuro` por caminho
   independente, blocos em ordem de tempo, cada bloco com as 3 classes.

Nada de `arvore`, `ajuste` e `replay` é afrouxado: todas as checagens deles têm de passar com os dados novos.

## Comandos

```bash
# Gold precisa do Java 17 (memória do projeto: java fora do PATH; o Silver já está em disco):
JAVA_HOME=/opt/homebrew/opt/openjdk@17 uv run python -m preditor gold
uv run python -m preditor arvore
uv run python -m preditor ajuste
uv run python -m preditor replay
uv run python -m preditor servir   # abrir a página e conferir o painel da árvore e o placar
```

Antes de refazer o Gold, copiar `data/gold/` e `data/modelo/` para `data/gold_antes_do_piso/` e
`data/modelo_antes_do_piso/` (ignoradas pelo git). Referência de código: commit `055c422`.

## Estrutura do projeto

```
src/preditor/
  config.py                    → PISO_AUMENTO_FALHA_PCT (+ comentário)
  gold/calculo_y/rotulo.py     → linha 3 com o piso
  __main__.py                  → checagens 1 a 4 acima
web/arvore.js                  → largura proporcional às folhas, rolagem e foco no caminho
SPEC-calculo-y.md              → decisão 5 revista (rótulo com piso, data e motivo)
docs/relatorio_analise_arvore.md → nova seção 8 (antes × depois); as seções 1 a 7 não são reescritas
AGENTS.md                      → estágio, decisões e comandos atualizados
```

## Estilo de código

Segue o `AGENTS.md`: nome em português, número mágico em `config.py` com a origem, o código comenta o passo e cita a
RFC. Exemplo do que a linha 3 deve parecer:

```python
# RFC §8.4, linha 3 + piso (decisão do dono, 09/10/2026, SPEC-piso-regra3.md): z extremo só é FALHA quando o RTT
# também subiu o suficiente. Piso None = a regra da RFC ao pé da letra.
falha_por_z = F.col("z_robusto") >= config.Z_FALHA
if config.PISO_AUMENTO_FALHA_PCT is not None:
    falha_por_z = falha_por_z & (F.col("aumento_pct") >= config.PISO_AUMENTO_FALHA_PCT)
```

## Estratégia de teste

Não há framework de testes (decisão do projeto): a verificação é rodar o pipeline com as checagens acima.
Além delas, conferências manuais, uma vez, ao fim:

- `features_B.parquet` novo = o anterior, coluna a coluna (o X não mudou);
- com `PISO_AUMENTO_FALHA_PCT = None`, o Gold sai idêntico ao de `data/gold_antes_do_piso/` (a chave de volta funciona);
- as contagens por regra e a tabela de destino batem com as da seção "A regra nova" (referência, não constante).

## Limites

- **Sempre:** rodar o pipeline completo (`gold` → `arvore` → `ajuste` → `replay`) depois da mudança; reportar o ganho
  sobre a persistência com as duas comparações (validação e, no relatório, a dobra interna); não comparar F1 entre
  rótulos; manter o teste fechado.
- **Perguntar antes:** mudar `CASAS_LIMIAR_REGRA`, `TOLERANCIA_ESCOLHA`, a grade ou o peso; incluir outros pisos
  (ms, duas medições seguidas); qualquer mudança no X.
- **Nunca:** editar a RFC; abrir o teste; tirar uma checagem para o pipeline passar; commitar `data/`; commitar sem o
  dono pedir.

## Critérios de sucesso

1. `gold`, `arvore`, `ajuste` e `replay` terminam com todas as checagens passando, sem checagem removida ou afrouxada
   (a `ok_com_z_extremo` é substituída por outra mais forte, não apagada).
   **Estado (10/10/2026): cumprido.** `gold` terminou com `exit 0` nas duas configurações (P2); `arvore` e `ajuste` (P3) e
   `replay` (P5) terminaram com as checagens. A `ok_com_z_extremo` virou a checagem 1 com o piso (`src/preditor/__main__.py`).
   Evidência: `tasks/todo-piso-regra3.md` (P2 a P5) e `data/analise_piso_regra3/conferir_rotulo_piso.log`.
2. `features_B.parquet` idêntico ao anterior; só mudam `regra`, `status_atual`, `status_futuro` (e o conteúdo dos
   arquivos de contagem).
   **Estado: cumprido.** `features_B` igual nas duas versões, e as 24 colunas do dataset que não são de rótulo iguais pela
   chave (`data/analise_piso_regra3/robustez_piso.log`). Mudam só `regra`, `status_atual`, `status_futuro` e
   `contagem_classes.csv`.
3. Todas as linhas com z ≥ 3,5 e `aumento_pct` ≥ 30 % estão na regra 1, 2 ou 3; nenhuma linha com `aumento_pct` < 30 %
   está na regra 3. A tabela de destino das rebaixadas é impressa.
   **Estado: cumprido.** Com piso 30, o Gold imprime o destino (14.370: 5 para FALHA, 2.929 para RISCO, 11.436 para OK) e as
   checagens passam (`conferir_rotulo_piso.log`). Na regra 3 restam 1.935 medições, todas com z ≥ 3,5 e aumento ≥ 30 %
   (`data/analise_piso_regra3/destino_rebaixadas.csv`).
4. Com o piso em `None`, o Gold é o de antes (reversão em uma linha).
   **Estado: cumprido.** Com `None`, o rótulo (regra, `status_atual`, `status_futuro`, `bloco`) é igual ao de
   `data/gold_antes_do_piso/` em 70.616 linhas, e as checagens do Gold passam. Feito em memória, sem gravar
   (`data/analise_piso_regra3/conferir_rotulo_piso.log`).
5. Relatório com a seção 8: antes × depois (persistência, árvore da Tarefa 3, ajustada sem e com peso, tamanhos,
   OK → FALHA, recall) e as ressalvas medidas (IC, dobra interna, queda do recall de FALHA, tamanho das árvores).
   **Estado: cumprido.** Seção 8 de `docs/relatorio_analise_arvore.md`: antes × depois (8.3), IC 95 % por fluxo e dobra
   interna (8.4) e as ressalvas medidas (8.5), com o ganho sem prova de ser maior, a árvore com 29 e 40 folhas e a
   queda do recall de FALHA.
6. O painel da página mostra as duas árvores completas e legíveis; o placar e a matriz ao fim do replay são iguais aos
   CSVs; nenhuma regressão no mapa.
   **Estado: cumprido (evidência de P5 e P6; nesta etapa a página não mudou).** `replay` com todas as checagens; placar e
   matriz da oficial ao fim do replay iguais a `matriz_validacao.csv`; as duas árvores legíveis, com rolagem, sem erro de
   console (`tasks/todo-piso-regra3.md`, P6).
7. Docs desatualizados corrigidos (lista abaixo), cada número novo vindo da execução e não do protótipo.
   **Estado: cumprido, com uma exceção que é do dono.** Atualizados: `AGENTS.md`, `SPEC-calculo-y.md` (decisão 5),
   `SPEC-ajuste-arvore.md` (nota e respostas), `SPEC-arvore-na-pagina.md` (nota de P6), `docs/relatorio_analise_arvore.md`
   (nota e seção 8), `docs/README.md` e a memória do projeto. O `README.md` da raiz (fora da lista) teve a referência a
   31 nós trocada. `data/README.md` não descreve a regra 3, então não mudou. Não editados, por regra: a RFC e os diários
   das tarefas. O registro no diário da Tarefa 4 (seção 4) fica com o dono. Os números novos vêm de
   `data/analise_piso_regra3/numeros_secao8.csv`.

## Documentos que ficam desatualizados (e serão corrigidos na implementação)

- `AGENTS.md`: estágio atual; "Limitação conhecida da regra 3"; "Recall de FALHA da ajustada cai (0,779 → 0,754)";
  "Teto conhecido dos dados" (0,77, 13 %, 68 %); "Peso de classe" (a pergunta à professora está respondida);
  "Folga" e checagens do Gold/Árvore/Replay; "A árvore ajustada ... 16 folhas / 31 nós"; a frase "o `arvore` e o `replay`
  com saídas idênticas" (acaba: o alvo mudou, só o código continua igual).
- `SPEC-calculo-y.md`: decisão 5 (era "regra da professora, sem piso").
- `SPEC-ajuste-arvore.md`: a promessa de saída idêntica da Tarefa 3 e as tabelas de referência (valem para o rótulo
  anterior; ficam como histórico, com nota).
- `SPEC-arvore-na-pagina.md` e `web/arvore.js`: 16 folhas / 31 nós / 1280 px.
- `docs/relatorio_analise_arvore.md`: ganha a seção 8; as seções 1 a 7 valem para o rótulo anterior (nota no topo).
- `docs/projeto_preditor_redes/tarefas/Tarefa4_Ajuste_da_Arvore.md` diz "mesmo rótulo": é o texto da professora, não se
  edita; o registro do que mudou vai no diário (seção 4, revisão com o docente), e o dono leva isto a ela.
- `tasks/todo-*.md` com números de referência: não são reescritos; valem para o rótulo anterior.

## Decisões fechadas (09/10/2026, pelo agente, por delegação do dono)

1. **Só a regra 3.** A regra 3 é a única com um limite natural dentro da própria tabela (os 30 % do RISCO) e 88 % dos
   casos abaixo dele. A regra 1 (1 pacote em 3 perdido = FALHA) é escolha explícita da RFC e perda de pacote é
   sinal real, não artefato de MAD pequeno. Se a professora tiver outra regra em mente, é uma spec nova.
2. **Árvores maiores no painel: aceitar o tamanho e desenhar com rolagem.** A regra de escolha da Tarefa 3 e a da
   Tarefa 4 são decisões do dono, tomadas antes de existir este rótulo, e escolher a regra depois de ver o resultado
   seria ajustar o método ao número. O painel passa a ter largura proporcional às folhas (80 por folha) e rolagem
   horizontal que leva o caminho em foco para a tela. Se o tamanho incomodar na revisão, apertar a regra é uma
   decisão à parte, medida então.
3. **Autorização:** o dono leva a liberação da professora ao diário da Tarefa 4 (seção 4). O diário é texto do grupo e
   o agente não o edita. Esta spec e o relatório ficam como o registro técnico.
4. **Peso:** mantém-se {OK 1, RISCO 2, FALHA 1,5}, salvo se a varredura no rótulo novo achar outra combinação que ganhe
   por mais de 0,005 de F1 macro **na validação e na dobra interna** (suposição 5). Sem isso, trocar peso é ajustar ao
   ruído: no rótulo atual 30 combinações ficaram dentro de ±0,003.
