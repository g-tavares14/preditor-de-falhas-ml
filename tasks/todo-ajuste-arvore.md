# Tarefas: Ajuste da árvore (Tarefa 4)

Spec: `SPEC-ajuste-arvore.md`. Plano: `tasks/plan-ajuste-arvore.md`.
Uma tarefa por vez; cada uma para para revisão do dono. Nada é commitado sem o dono pedir.

## Fase 1: base

- [x] **A1: cópia de referência das saídas de hoje**
  - Descrição: antes de mexer em código, guardar fora do repositório (pasta temporária) uma cópia de `data/modelo/`,
    de `web/dados/replay.json` e das colunas atuais de `features_B.parquet` e `dataset_rotulado_B.parquet`.
  - Aceite: a cópia existe e `arvore` + `replay`, rodados agora, reproduzem exatamente os arquivos copiados.
  - Verificação: `uv run python -m preditor arvore && uv run python -m preditor replay`, depois `diff -r` com a cópia.
  - Depende de: nada. Arquivos: nenhum do repositório. Tamanho: XS.

- [x] **A2: `min5_z` e `media5_z` no Gold**
  - Descrição: calcular as duas colunas em `_metricas_da_janela`, com a janela `ultimas`; somar as checagens ao
    `_verificar_gold`; pôr `COLUNAS_AJUSTE` em `config.py`.
  - Aceite:
    - `features_B` e `dataset_rotulado_B` têm as duas colunas, as 70.616 linhas de antes e as colunas antigas
      idênticas à cópia de A1;
    - o Gold para se `min5_z` > `media5_z`, se `min5_z` > `z_robusto`, se o caminho independente (auto-junção das 4
      anteriores) discordar, ou se houver nulo com algum z na janela;
    - as checagens antigas do Gold continuam passando.
  - Verificação: `uv run python -m preditor gold`; comparação das colunas antigas com a cópia.
  - Depende de: A1. Arquivos: `gold/calculo_x/features.py`, `__main__.py`, `config.py`. Tamanho: M.

- [x] **A3: `DadosModelo` conhece as colunas novas sem pô-las no X oficial**
  - Descrição: a checagem de "coluna sem decisão" aceita `COLUNAS_AJUSTE`; as colunas novas ficam à parte, com um
    método que entrega o X ajustado (10 colunas, `float64`, ausente continua ausente); a região da validação entra
    num caminho de localização, fora de qualquer X.
  - Aceite:
    - `dados.X[bloco]` continua com exatamente as 8 colunas;
    - o X ajustado tem as 8 + 2, na ordem, mesmo índice do `y`, nenhuma proibida, mesmos nulos do Gold;
    - `arvore` e `replay` dão arquivos idênticos à cópia de A1.
  - Verificação: `uv run python -m preditor arvore && uv run python -m preditor replay`; `diff -r` com a cópia.
  - Depende de: A2. Arquivos: `modelo/dados.py`, `config.py`. Tamanho: S.

### Checkpoint 1 (depois de A3)

- [ ] `gold`, `arvore` e `replay` passam em todas as checagens
- [ ] Saídas da Tarefa 3 iguais à cópia de referência
- [ ] Revisão do dono antes de seguir

## Fase 2: a árvore ajustada

- [x] **A4: `ArvoreAjustada`: busca nas duas variantes e regra de escolha**
  - Descrição: `modelo/ajuste.py` com a busca (grade da Tarefa 3 × Gini / entropia, sem peso e com peso), a função
    pura da regra de escolha (tolerância de 0,005, vence a mais simples) e a descrição para o JSON. `_ajustar` de
    `ArvoreBase` ganha critério, peso e colunas opcionais, com os valores de hoje como padrão. Constantes em `config.py`.
  - Aceite:
    - 56 combinações por variante, todas com `fit` só no treino e nas 10 colunas;
    - a escolhida de cada variante é a mais simples dentro da tolerância, e a função da regra dá o mesmo resultado
      quando recebe a tabela relida;
    - mesma semente = mesma árvore; `arvore` continua idêntico à cópia de A1.
  - Verificação: script curto imprimindo a busca e a escolhida das duas variantes (F1 da com peso entre 0,75 e
    0,77; fora disso, parar); `uv run python -m preditor arvore` + `diff`.
  - Depende de: A3. Arquivos: `modelo/ajuste.py` (novo), `modelo/arvore.py`, `config.py`. Tamanho: M.

- [x] **A5: medidas novas na avaliação**
  - Descrição: em `avaliacao.py`, funções à parte de `medir`: acerto quando o futuro muda, acerto por transição
    (agora → futuro) e F1 macro por região, com as checagens de soma.
  - Aceite:
    - as linhas "futuro muda" + "futuro igual" somam o N da validação; as 9 transições e as regiões também;
    - para a árvore da Tarefa 3 os valores batem com o relatório (23,4 % quando muda; Brasil 0,479);
    - `Avaliacao.medir` e o teste fechado não mudam (o bloco de teste continua recusado).
  - Verificação: script curto com a persistência e a árvore da Tarefa 3; `uv run python -m preditor arvore` + `diff`.
  - Depende de: A3. Arquivos: `modelo/avaliacao.py`. Tamanho: S.

- [x] **A6: comando `ajuste` de ponta a ponta**
  - Descrição: `modelo/execucao_ajuste.py` (`ExecucaoAjuste`) e a opção `ajuste` em `__main__.py`: carrega os dados,
    refaz e confere a árvore da Tarefa 3, busca as duas variantes, mede os quatro modelos, lê as 3 regras em
    português da ajustada (`Regras` aceitando o X por parâmetro), verifica tudo e só então grava e imprime o
    material do diário (tabela erro → mudança, parâmetros, regras, matriz, tabela Tarefa 3 → Tarefa 4, transições,
    regiões).
  - Aceite:
    - roda offline, sem Spark; sem Gold novo ou sem as saídas do `arvore`, diz qual comando rodar antes;
    - grava os 6 arquivos da spec e passa em todas as checagens da seção "Estratégia de testes";
    - `arvore` e `replay` continuam idênticos à cópia de A1; nenhum número do teste além do N.
  - Verificação: `uv run python -m preditor ajuste`; depois `arvore` e `replay` + `diff`.
  - Depende de: A4, A5. Arquivos: `modelo/execucao_ajuste.py` (novo), `modelo/regras.py`, `__main__.py`,
    `config.py`. Tamanho: M.

### Checkpoint 2 (depois de A6)

- [ ] `ajuste` passa de ponta a ponta e imprime tudo o que o diário pede
- [ ] `arvore` e `replay` iguais à cópia de referência
- [ ] Revisão do dono: os números reais (em Spark) contra os do relatório

## Fase 3: documentação

- [x] **A7: documentos**
  - Descrição: `AGENTS.md` (estágio, comando, checagens, decisões), `README.md`, `data/README.md` (colunas e
    arquivos novos; não foi alterado: ele só documenta a fonte dos dados, sem dicionário de colunas), índice de `docs/README.md` (relatório), `tasks/` e a referência de resultados neste arquivo.
  - Aceite: os documentos descrevem o comando `ajuste`, as duas colunas, o peso (com a pendência da professora) e
    a regra de escolha; os critérios de sucesso da spec estão marcados.
  - Verificação: leitura; `uv run python -c "import preditor.__main__"`.
  - Depende de: A6. Arquivos: `AGENTS.md`, `README.md`, `data/README.md`, `docs/README.md`,
    `SPEC-ajuste-arvore.md`. Tamanho: S.

### Checkpoint 3 (depois de A7)

- [ ] Todos os critérios de sucesso da spec marcados
- [ ] Revisão final do dono

## Referência de resultados

Execução de 02/10/2026 (`uv run python -m preditor ajuste`), validação com N = 13.490 (treino 34.661). São
resultado, não constante: nenhum deles está em `config.py`.

| Modelo | Escolhida | Folhas | F1 macro | Recall FALHA | Recall RISCO | Acerto quando o futuro muda |
|---|---|---|---|---|---|---|
| persistência | | | 0,7221 | 0,8092 | 0,4879 | 0,0 % |
| árvore da Tarefa 3 | Gini 4 / 50 | 16 | 0,7457 | 0,7786 | 0,4904 | 23,4 % |
| ajustada sem peso | Gini 2 / 500 | 4 | 0,7553 | 0,7224 | 0,6010 | 35,9 % |
| ajustada com peso (adotada) | Gini 4 / 100 | 16 | 0,7600 | 0,7543 | 0,5643 | 33,3 % |

- Maior F1 puro da busca: 0,7596 sem peso (Gini 6 / 50, 55 folhas) e 0,7641 com peso (Gini 10 / 50, 187 folhas).
- Com peso, 4 / 100 e 4 / 50 dão a mesma árvore em F1 (0,7600); a regra fica com a de folha mínima maior.
- Importância na adotada: `min5_z` 0,753, `n5_moderado` 0,194, `z_robusto` 0,020, `n5_aumento80` 0,018, `media5_z` 0,014.
- O Spark reproduz o protótipo em pandas do relatório (diferença máxima de 2e-13 em `media5_z`).

Desvios do plano, decididos na A6:

- **Casas do limiar:** as regras em português da ajustada usam 6 casas (`CASAS_LIMIAR_REGRA_AJUSTE`). Com as 4 da
  Tarefa 3, o limiar impresso selecionava linhas diferentes das da folha. O texto da Tarefa 3 segue com 4.
- **Pureza com peso de classe:** `Regras.verificar` passou a dividir `tree_.value` pelo peso de cada classe antes
  de conferir a pureza (com peso, `value` é ponderado). Sem peso, divide por 1: a Tarefa 3 não muda.
