# Spec: Ajuste da árvore (Tarefa 4)

Status: **aprovada pelo dono em 02/10/2026**.

> **Nota (10/10/2026):** os números de referência desta spec (tabelas, a promessa de saída idêntica da Tarefa 3, F1 e
> recalls) valem para o rótulo anterior ao piso da regra 3 (commit `055c422`). Ficam como histórico. O rótulo atual está
> em `SPEC-piso-regra3.md`, e os números dele, na seção 8 de `docs/relatorio_analise_arvore.md`.

## Objetivo

Ajustar a árvore da Tarefa 3 a partir do que ela errou e entregar o que o diário da Tarefa 4 pede
(`docs/projeto_preditor_redes/tarefas/Tarefa4_Ajuste_da_Arvore.md`, 05/10 a 11/10/2026): a árvore ajustada, as
regras novas em português, a matriz 3×3 na validação e a tabela Tarefa 3 → Tarefa 4 (F1 macro, recall de FALHA e de
RISCO). A justificativa e os números de referência estão em `docs/relatorio_analise_arvore.md`.

**As duas árvores ficam** (decisão do dono, 02/10/2026): a da Tarefa 3 continua sendo treinada e gravada como hoje,
sem nenhuma mudança de resultado; a ajustada nasce ao lado, num comando próprio, e é medida contra ela.

### O que não muda

- Alvo (`status_futuro`), rótulo, baseline, corte dos blocos, folga, semente 16, `fit` só no treino.
- Continua árvore de decisão (CART do scikit-learn). Nenhum outro algoritmo.
- O teste continua fechado até a Tarefa 5.
- O comando `arvore` e as saídas dele: mesmas 8 colunas, mesma árvore, mesmos arquivos, byte a byte.
- O `replay` e a página: continuam mostrando a árvore da Tarefa 3.

### Erro da Tarefa 3 → mudança (diário, seção 1)

| Erro observado na validação | Mudança |
|---|---|
| Pico isolado virando FALHA: quando o agora é FALHA e o futuro é OK (488 casos), a árvore acerta 16,4 % | coluna nova `min5_z` |
| RISCO sumindo: recall de RISCO 0,49; previstos 1.317 contra 1.609 reais | coluna nova `media5_z` e peso de classe (ver "Decisões fechadas", 1) |
| A árvore repete o agora: igual ao `status_atual` em 92,6 % das linhas; acerta 23,4 % quando o futuro muda | as duas colunas novas (dão o histórico recente do `z_robusto`) |

### Colunas novas (Gold, cálculo do X)

Duas métricas relativas ao baseline, como o diário permite ("tendência do `z_robusto` nas janelas anteriores"):

- **`min5_z`**: o menor `z_robusto` das últimas 5 medições do fluxo (a atual + 4 anteriores). Alto = o desvio se
  manteve nas 5; baixo com `z_robusto` alto = pico isolado.
- **`media5_z`**: a média do `z_robusto` nas mesmas 5 medições.

Regras de cálculo:

- Mesma janela das `n5_` (`config.JANELA`, `rowsBetween(-4, 0)` por `fluxo_id`, ordenada por `t`): nunca olha o futuro.
- `z_robusto` nulo (medição sem RTT) é ignorado no mínimo e na média; se as 5 forem nulas, a coluna fica nula. Nada
  é imputado (RFC §8.3).
- No começo do Período B a janela tem menos de 5 medições: usa as que existem, como as `n5_` já fazem. Nada do
  Período A entra.
- Entram em `features_B.parquet` e seguem para `dataset_rotulado_B.parquet`. O cálculo do Y não as lê.

Colunas da árvore ajustada: as 8 da Tarefa 3 + `min5_z` + `media5_z` (10 colunas). As 8 ficam em `COLUNAS_ARVORE`,
intocada; as duas novas, numa lista à parte (`COLUNAS_AJUSTE`). País, região, IP, rota, `fluxo_id`, `rtt`,
`status_atual` e `regra` continuam proibidos.

### Como a árvore ajustada é escolhida (diário, seção 2)

- Grade: `max_depth` ∈ {2, 3, 4, 5, 6, 8, 10} × `min_samples_leaf` ∈ {50, 100, 200, 500} (a mesma da Tarefa 3) ×
  critério ∈ {Gini, entropia}: 56 árvores por variante de peso. `fit` só no treino.
- **Regra de escolha:** entre as árvores com F1 macro da validação a até **0,005** do melhor, vence a mais simples
  (menor `max_depth`, depois `min_samples_leaf` maior, depois Gini). O melhor F1 puro levaria a 187 folhas por
  +0,004; diferenças abaixo de 0,007 estão dentro do ruído medido (relatório, seção 4).
- **Peso de classe:** {OK 1, RISCO 2, FALHA 1,5}. A árvore é buscada nas duas variantes (sem peso e com peso) e as
  duas entram na tabela de comparação; a variante que vira "a árvore ajustada" é a com peso (ver "Decisões
  fechadas", 1).
- Poda por custo (`ccp_alpha`) fica fora: no relatório não passou das combinações acima.
- Saem, como na Tarefa 3: critério, hiperparâmetros pedidos e obtidos, folhas, divisões dos dois primeiros níveis,
  árvore inteira em texto e 3 regras em português (as folhas mais cheias, uma por classe), reutilizando `Regras`.

Referência do protótipo (pandas, fora do Gold; os valores podem mudar um pouco com o cálculo em Spark):

| Variante | Escolhida pela regra | Folhas | F1 macro | Recall RISCO | Recall FALHA |
|---|---|---|---|---|---|
| Árvore da Tarefa 3 | Gini 4 / 50 | 16 | 0,7457 | 0,490 | 0,779 |
| Ajustada sem peso | Gini 2 / 500 | 4 | 0,7553 | 0,601 | 0,722 |
| Ajustada com peso | Gini 4 / 50 | 16 | 0,7600 | 0,564 | 0,754 |

Esses números são referência, não constante: não vão para `config.py` nem são checados contra valor fixo.

### Comparação na validação (diário, seção 3)

Para a persistência, a árvore da Tarefa 3, a ajustada sem peso e a ajustada com peso, nas mesmas linhas:

- matriz 3×3 em contagem; precisão, recall e F1 por classe; F1 macro; balanced accuracy; acurácia;
- **tabela Tarefa 3 → Tarefa 4**: F1 macro, recall de FALHA e recall de RISCO;
- **acerto quando o futuro muda** (linhas com `status_futuro` ≠ `status_atual`) e acerto por transição
  (OK → FALHA, OK → RISCO, FALHA → OK, RISCO → OK);
- **F1 macro por região de destino**, com a persistência ao lado. Região aqui só agrupa o resultado: não entra no X.
- Se não houver ganho, o programa imprime isso; não se troca alvo nem rótulo.

### Fora do escopo

- Medir o teste, Protocolo B, ficha da árvore: Tarefa 5.
- Trocar a árvore do `replay` e da página.
- Outras colunas testadas no relatório (`incl5_z`, `n10_z35`, `d1_z` etc.) e as 5 extras do Gold.
- Preencher o diário e o dicionário v0.3: o programa imprime tudo pronto para colar; o texto é do grupo.

## Stack

A mesma: PySpark 3.5 no Gold; scikit-learn ≥ 1.4, pandas e pyarrow na árvore. Nenhuma dependência nova.

## Comandos

```bash
uv run python -m preditor gold     # refaz o Gold com as duas colunas novas (offline)
uv run python -m preditor arvore   # a árvore da Tarefa 3: tem de dar o mesmo resultado de antes
uv run python -m preditor ajuste   # novo: data/gold/ → data/modelo/ (offline, sem Spark nem Java)
uv run python -m preditor replay   # tem de continuar passando, sem mudança
```

`ajuste` é um comando à parte, fora da execução sem argumento. Sem o Gold, ou com um Gold antigo (sem as colunas
novas), termina com "Rode antes: uv run python -m preditor gold".

## Estrutura do projeto

```
src/preditor/
  config.py                    → COLUNAS_AJUSTE, peso de classe, grade e tolerância do ajuste, caminhos novos
  gold/calculo_x/features.py   → `min5_z` e `media5_z` em `_metricas_da_janela`
  modelo/dados.py              → aceita as colunas novas sem pô-las no X oficial; entrega o X ajustado à parte
                                 (mesmo desenho de `x_contraste`)
  modelo/ajuste.py             → classe ArvoreAjustada (herda de ArvoreBase): busca, regra de escolha, peso
  modelo/avaliacao.py          → acerto quando o futuro muda, por transição e por região
  modelo/execucao_ajuste.py    → classe ExecucaoAjuste: orquestra, verifica e grava
  __main__.py                  → opção `ajuste`
data/modelo/            (ignorado pelo git; os arquivos da Tarefa 3 não mudam)
  busca_ajuste.csv             → todas as combinações das duas variantes
  arvore_ajustada.json         → critério, hiperparâmetros, folhas, semente, peso, colunas
  regras_arvore_ajustada.txt   → árvore em texto + 3 regras em português
  matriz_ajuste.csv            → matrizes 3×3 dos quatro modelos
  metricas_ajuste.csv          → métricas dos quatro modelos, incluindo transições e regiões
  comparacao_t3_t4.csv         → a tabela do diário
```

## Estilo de código

Segue o `AGENTS.md`: português, um passo por linha, comentário com o porquê, constantes em `config.py` com a origem.

```python
# gold/calculo_x/features.py, dentro de `_metricas_da_janela` (mesma janela `ultimas` das n5_)
# Histórico do z nas últimas 5: `min` e `avg` do Spark ignoram o nulo (medição sem RTT), nada é imputado.
.withColumn("min5_z", F.min("z_robusto").over(ultimas))    # alto = desvio sustentado; baixo = pico isolado
.withColumn("media5_z", F.avg("z_robusto").over(ultimas))

# config.py
# SPEC-ajuste-arvore.md, "Colunas novas": só a árvore ajustada as vê; a da Tarefa 3 segue com as 8.
COLUNAS_AJUSTE = ["min5_z", "media5_z"]
# Relatório de 02/10/2026, seção 3.3: o peso com a melhor média entre os testados.
PESO_CLASSES_AJUSTE = {"OK": 1, "RISCO": 2, "FALHA": 1.5}
TOLERANCIA_ESCOLHA = 0.005  # F1 macro: dentro disso, vence a árvore mais simples
```

## Estratégia de testes

Sem framework de testes: a verificação é rodar os comandos, que param com `assert`.

Gold (novas checagens):

- `min5_z` ≤ `media5_z` em toda linha em que as duas existem; `min5_z` ≤ `z_robusto` quando o z existe;
- as duas conferidas por um caminho independente (auto-junção das 4 medições anteriores, sem a janela);
- nula só quando nenhuma das 5 medições tem z; mesmo número de linhas de antes (70.616).

`arvore` (regressão): X com exatamente as 8 colunas; `arvore_oficial.json`, a matriz e as métricas iguais às de antes
da mudança (comparadas com uma cópia guardada antes de mexer). `replay` continua passando.

`ajuste` para se:

- o X ajustado não tiver exatamente as 10 colunas, ou tiver alguma proibida;
- houver linha de validação ou teste no `fit`, ou linha de teste em qualquer métrica;
- a árvore da Tarefa 3 refeita aqui não for igual a `arvore_oficial.json`, ou suas métricas não baterem com
  `metricas_validacao.csv`;
- a escolhida não for a mais simples dentro da tolerância, conferida de novo a partir de `busca_ajuste.csv`;
- alguma matriz não somar o N da validação, ou o F1 macro não bater com a média dos três F1 da matriz;
- as linhas por região, ou por transição, não somarem o total;
- as regras citarem coluna fora das 10, ou uma regra não selecionar exatamente as linhas da folha;
- treinar de novo com a mesma semente der outra árvore.

## Limites

- **Sempre:** `fit` só no treino; escolha só pela validação; medir persistência e Tarefa 3 nas mesmas linhas;
  constantes em `config.py` com a origem; atualizar `AGENTS.md`, `README.md` e os READMEs de `data/`.
- **Perguntar antes:** outra coluna nova; outro peso; mudar a grade ou a tolerância; trocar a árvore do `replay`;
  qualquer dependência nova; qualquer mudança no Gold além das duas colunas.
- **Nunca:** ler o teste para medir ou escolher; mudar o resultado do comando `arvore`; usar país, região, IP, rota,
  `fluxo_id`, `rtt`, `status_atual` ou `regra` como coluna; recalcular o baseline; commitar dados ou modelos.

## Critérios de sucesso

- [x] `uv run python -m preditor gold` grava as duas colunas e passa nas checagens novas e nas antigas.
- [x] `uv run python -m preditor arvore` dá a mesma árvore e as mesmas métricas de antes.
- [x] `uv run python -m preditor replay` continua passando.
- [x] `uv run python -m preditor ajuste` roda offline e passa em todas as checagens.
- [x] A saída traz a tabela erro → mudança, os parâmetros da ajustada, as 3 regras em português, a matriz 3×3 e a
      tabela Tarefa 3 → Tarefa 4 (F1 macro, recall de FALHA, recall de RISCO).
- [x] A saída traz o acerto quando o futuro muda e o F1 por região, para os quatro modelos.
- [x] Nenhum número do teste aparece além do N.
- [x] `AGENTS.md` e `README.md` descrevem o comando, as colunas novas e as decisões.

## Premissas

1. As duas árvores ficam; a da Tarefa 3 não muda em nada (confirmado pelo dono em 02/10/2026).
2. As colunas novas entram no Gold, e não num cálculo à parte em pandas: o X do projeto nasce numa camada só.
3. Entram só `min5_z` e `media5_z`. A `incl5_z` do relatório fica fora: só é usada em árvores com mais de 16 folhas.
4. A janela das colunas novas é a mesma das `n5_` (por linhas, sem conferir o intervalo de tempo entre elas).
5. O `replay` continua na árvore da Tarefa 3.
6. `ajuste` é um comando à parte e grava arquivos próprios, sem tocar nos da Tarefa 3.

## Decisões fechadas (02/10/2026)

O dono aprovou as propostas da spec:

1. **Peso de classe:** as duas variantes são medidas; a árvore ajustada é a **com peso** {OK 1, RISCO 2, FALHA 1,5}.
   O diário lista como ajuste permitido "profundidade, mínimo de amostras na folha, critério e poda", mais coluna
   relativa nova, e peso de classe não está na lista: a pergunta vai à professora na revisão (seção 4 do diário). Se
   ela vetar, a ajustada passa a ser a sem peso, trocando uma constante.
2. **Regra de escolha:** tolerância de 0,005 no F1 macro, vencendo a árvore mais simples.
3. **Entropia na grade:** fica; no empate a regra prefere Gini.
4. **Recall de FALHA:** a regra de escolha não o exige. No protótipo ele cai nas duas variantes (0,754 e 0,722 contra
   0,779 da Tarefa 3); o número sai na tabela e a queda é explicada na leitura do ganho. A spec foi aprovada assim;
   se o dono preferir exigir que ele não caia, muda a regra de escolha antes do `/build`.

## Resultado e pendências da revisão (02/10/2026)

Implementada em 02/10/2026; números reais em `tasks/todo-ajuste-arvore.md` e leitura em
`docs/relatorio_analise_arvore.md`, seção 7. A ajustada adotada (Gini 4 / 100, 16 folhas, com peso) tem F1 macro
0,7600 na validação, contra 0,7457 da Tarefa 3.

Dois desvios do que a spec previa, decididos na implementação:

- As regras em português da ajustada usam 6 casas no limiar (`CASAS_LIMIAR_REGRA_AJUSTE`); com as 4 da Tarefa 3, o
  limiar impresso selecionava linhas diferentes das da folha.
- Com peso de classe, `tree_.value` é ponderado: `Regras.verificar` desconta o peso antes de conferir a pureza.

Pendências para a revisão com a professora (seção 4 do diário):

1. **Peso de classe:** não está na lista de ajustes permitidos. Se for vetado, troca-se `MODELO_AJUSTADA`.
   **Resposta (09/10/2026):** a professora liberou pesos de classe (relato do dono); o peso foi mantido em 10/10/2026
   (`SPEC-piso-regra3.md`, seção 8.6 do relatório).
2. **Regra 3 do rótulo:** 68 % dos episódios de FALHA duram uma medição; perguntar se a Tarefa 5 pode dar um piso à
   regra ou exigir duas medições seguidas. Até lá, a regra dela continua.
   **Resposta (09/10/2026):** a professora liberou pisos nas regras (relato do dono), e o piso foi aplicado
   (`SPEC-piso-regra3.md`). Duas medições seguidas não foram testadas.

Limitação conhecida: nenhum modelo testado, nem um boosting de 300 árvores com 20 colunas, passa de 0,77 de F1 macro
nem de 13,4 % de acerto em OK → FALHA. O teto vem dos dados (relatório, seção 7.1; valores do rótulo anterior ao piso, não refeitos: seção 8.5).
