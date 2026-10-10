# Plano: Replay da apresentação com a Random Forest

Spec: `SPEC-replay-floresta.md` (aprovada pelo dono em 10/10/2026). Tarefas: `tasks/todo-replay-floresta.md`.

## Resumo

O `replay` passa a prever com o `modelo_final.joblib` (arquivo, SHA-256 conferido) em vez de refazer a árvore, grava no JSON
um bloco `modelo` e tira o que era só da árvore (`arvores`, `folha`, `x`, regras). As checagens da árvore são trocadas por
checagens contra a comparação. A página só ganha o nome do modelo. `arvore`, `ajuste`, `comparar`, `exportar` e `teste`
não mudam.

## Decisões de arquitetura

- **O modelo é o arquivo.** Reaproveitar a leitura e a conferência do `.joblib` que o `teste` já faz (`execucao_teste.py`:
  SHA-256 contra o `LEIA-ME.md`, família, colunas); não reimplementar. Se o reaproveitamento exigir mexer em
  `execucao_teste.py`, extrair a função para um lugar comum SEM alterar o carimbo do ensaio do teste (o hash de código dele
  entra no carimbo: se mudar, o ensaio precisa rodar de novo e isso deve ser dito). Alternativa preferida: um pequeno módulo
  novo de leitura do `.joblib` usado só pelo `replay`, copiando a conferência (sem tocar nos módulos do `teste`).
- **X de 10 colunas** do bloco exibido, na ordem das colunas gravadas no `.joblib`; `NaN` continua `NaN`.
- **JSON enxuto.** Saem `arvores`, `folha`, `x` e as regras; fica `modelo` (nome, família, n de árvores, parâmetros,
  SHA-256, colunas). Nada de métrica nem rótulo calculado no navegador.
- **Checagens novas** (substituem as da árvore): previsões do JSON = recarga do modelo; matriz e F1 do placar recalculados do JSON
  = linhas `random_forest` e `persistencia` de `comparacao/matriz_comparacao.csv` e `comparacao_modelos.csv`. Mantidas: sem
  teste no JSON, `t_futuro` independente, rotas, determinismo (mesma entrada = mesmo JSON).
- **`replay` deixa de exigir `ajuste`;** exige `exportar` e `comparar` (cada um diz qual comando rodar antes).
- **A página só lê `modelo.nome` e `modelo.arvores`** do JSON, com `textContent`.

## Grafo de dependências

```
R1 exportador e execução do replay com a floresta (JSON enxuto, checagens novas)
 └─ R2 página: nome do modelo e texto "validação"; verificar no navegador
     └─ R3 documentos: AGENTS.md, SPEC-visualizacao.md, verificação de identidade dos outros comandos
```

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Remover campos do JSON quebra algum JS ou o `verificar-carga.js` | Médio | `grep` por `arvores`, `folha`, `.x` em `web/`; abrir a página e ver o console; ajustar o `verificar-carga.js` |
| O placar do JSON não bate com a comparação | Médio | É o objetivo da checagem: se não bater, para-se e relata-se, sem afrouxar |
| Mexer em módulos do `teste` invalida o carimbo do ensaio | Médio | Não mexer neles (módulo novo); se for inevitável, avisar o dono |
| A plateia estranha 0,70 na página contra 0,67 no relatório | Baixo | Texto da página diz "validação" (R2) e o guia da apresentação explica a diferença |
| O Gold/JSON gerados antes continuam em `web/dados/` | Baixo | `replay` regrava; o arquivo é ignorado pelo git |

## Verificação

- **R1:** `uv run python -m preditor replay` termina com todas as checagens; o JSON só tem os campos novos; sem linha do teste.
- **R2:** `servir` + navegador embutido: abre, toca o replay até o fim, placar igual ao do JSON e à comparação; console limpo; largura de notebook e de tela grande.
- **R3:** `arvore`, `ajuste`, `comparar`, `exportar`, `teste --ensaio` (sem abrir o teste) com saídas idênticas.

## Skills do catálogo

Nenhuma é necessária (a verificação visual usa o navegador embutido).
