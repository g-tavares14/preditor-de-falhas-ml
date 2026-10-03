# Plano: Ajuste da árvore (Tarefa 4)

Spec: `SPEC-ajuste-arvore.md` (aprovada em 02/10/2026). Tarefas: `tasks/todo-ajuste-arvore.md`.
Justificativa e números de referência: `docs/relatorio_analise_arvore.md`.

## Resumo

Duas colunas novas no Gold (`min5_z`, `media5_z`) e um comando novo, `ajuste`, que busca a árvore ajustada em duas
variantes (sem peso e com peso de classe), escolhe pela validação com a regra da tolerância e a compara com a
persistência e com a árvore da Tarefa 3. O comando `arvore`, as saídas dele e o `replay` não mudam de resultado.

## Decisões de arquitetura

- **As colunas novas nascem no Gold**, em `Features._metricas_da_janela`, com a janela `ultimas` que já existe. O
  cálculo do Y não as lê, mas elas seguem para `dataset_rotulado_B.parquet` porque o rótulo parte das features.
- **`COLUNAS_ARVORE` não muda.** As duas novas ficam em `COLUNAS_AJUSTE`. `DadosModelo` guarda-as à parte e entrega o
  X ajustado por um método próprio, no mesmo desenho de `extras_contraste` / `x_contraste`. Assim o X oficial, o
  `arvore` e o `replay` (que usam `COLUNAS_ARVORE`) continuam com as 8.
- **A checagem "coluna do Gold sem decisão"** de `DadosModelo._verificar` passa a aceitar três listas:
  `COLUNAS_ARVORE`, `COLUNAS_AJUSTE` e `COLUNAS_PROIBIDAS`.
- **`ArvoreAjustada` herda de `ArvoreBase`** (em `modelo/ajuste.py`) e tem a própria busca: grade × critério, por
  variante de peso. O `_ajustar` de `ArvoreBase` hoje fixa critério, colunas e a ausência de peso; ele ganha
  parâmetros opcionais com os valores de hoje como padrão, para a árvore da Tarefa 3 sair idêntica.
- **A regra de escolha é uma função pura** sobre a tabela da busca (entra o quadro, sai a linha escolhida): a
  checagem a refaz a partir do CSV gravado.
- **`Regras` é reutilizada.** Ela lê `dados.X[bloco]`; passa a aceitar o X por parâmetro (padrão: o oficial).
- **As medidas novas** (acerto quando o futuro muda, por transição, por região) entram em `avaliacao.py` como
  funções à parte de `Avaliacao.medir`, que não muda. A região vem de `DadosModelo` por um caminho de localização,
  como `localizacao_validacao`, e nunca entra em X.
- **Arquivos próprios** em `data/modelo/` (`*_ajuste.csv`, `arvore_ajustada.json`, `regras_arvore_ajustada.txt`,
  `comparacao_t3_t4.csv`). Os da Tarefa 3 não são reescritos pelo `ajuste`: o `replay` os confere.
- **A árvore da Tarefa 3 é refeita dentro do `ajuste`** (mesma semente) e conferida contra `arvore_oficial.json` e
  `metricas_validacao.csv`, como o `replay` já faz. Sem esses arquivos: "Rode antes: uv run python -m preditor arvore".

## Grafo de dependências

```
A1 cópia de referência (arvore, replay)
 └─ A2 Gold: min5_z, media5_z + checagens
     └─ A3 DadosModelo: COLUNAS_AJUSTE, X ajustado, região    ── regressão: arvore e replay iguais à referência
         ├─ A4 ArvoreAjustada: busca nas duas variantes + regra de escolha
         │   └─ A6 comando `ajuste`: orquestra, regras, grava, verifica, imprime
         └─ A5 Avaliacao: futuro muda, transições, região ────┘
                                                               └─ A7 docs (AGENTS.md, README.md, data/README.md)
```

A4 e A5 não dependem uma da outra. A6 fecha a fatia de ponta a ponta.

## Riscos

| Risco | Mitigação |
|---|---|
| Mexer em `ArvoreBase._ajustar`, `Regras` ou `DadosModelo` muda a árvore da Tarefa 3 | A1 guarda as saídas de hoje; ao fim de A3, A4 e A6 roda-se `arvore` e `replay` e compara-se arquivo a arquivo |
| O Gold refeito muda alguma coluna antiga | A2 compara as colunas antigas de `features_B` e `dataset_rotulado_B` com a cópia de antes: têm de ser iguais |
| Os números em Spark diferem do protótipo em pandas | Esperado e pequeno. Os valores do relatório são referência, não constante; se o F1 da ajustada com peso sair fora de 0,75 a 0,77, parar e investigar antes de seguir |
| A regra da tolerância escolhe outra árvore que não a 4 / 50 | É resultado, não erro: registra-se o que saiu. A checagem confere a regra, não o valor |
| `F.min` / `F.avg` com nulo se comportam diferente do esperado | A checagem do Gold confere as duas colunas por um caminho independente (auto-junção, sem janela) |
| A professora vetar o peso de classe | As duas variantes já são medidas e gravadas; trocar a adotada é uma constante em `config.py` |

## Verificação

Sem framework de testes. Cada tarefa termina rodando o comando afetado, que para com `assert`. Checkpoints:

- **Depois de A3:** `gold`, `arvore` e `replay` passam; saídas da Tarefa 3 iguais à referência. Revisão do dono.
- **Depois de A6:** `ajuste` passa de ponta a ponta; `arvore` e `replay` continuam iguais. Revisão do dono.
- **Depois de A7:** todos os critérios de sucesso da spec marcados.

## Skills do catálogo

Nenhuma tarefa pede skill fora das instaladas.
