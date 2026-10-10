# Plano: Piso na regra 3 do rótulo

Spec: `SPEC-piso-regra3.md` (aprovada em 09/10/2026). Tarefas: `tasks/todo-piso-regra3.md`.
Justificativa e protótipo: conversa de 09/10/2026; referência anterior ao piso: commit `055c422`.

## Resumo

Uma condição a mais na linha 3 do Y (`aumento_pct` ≥ 30 %), com chave de reversão em `config.py`. O código quase todo
fica como está: o que muda é o **dado** (`regra`, `status_atual`, `status_futuro`), então `arvore`, `ajuste` e
`replay` são só rodados de novo. As mudanças de código são três: a linha 3 e as checagens do Gold, e o desenho do
painel da árvore, que foi feito para 16 folhas e agora recebe 29 e 40 (valores do protótipo).

## Decisões de arquitetura

- **A mudança do Y é uma condição em `Rotulo._regra`**, controlada por `config.PISO_AUMENTO_FALHA_PCT`
  (`= AUMENTO_RISCO_PCT`; `None` = RFC ao pé da letra). Nada mais do Gold muda: o X sai idêntico.
- **A reversão é testável.** Com o piso em `None` o Gold tem de sair idêntico ao de antes: é a prova de que o
  refatoramento da linha 3 não mexeu em mais nada, e fica como a chave de volta se a professora reconsiderar.
- **As checagens do Gold ficam mais fortes, não mais fracas.** `ok_com_z_extremo` (que falharia de propósito) é
  trocada por uma checagem com o piso, e ganha duas por outro caminho (regra 3 ⇒ piso; z e aumento altos ⇒ regra 1 a 3).
- **`modelo/` e `visualizacao/` não mudam.** Os números, o tamanho das árvores e a escolha dos hiperparâmetros são
  resultado. Se alguma checagem falhar por causa do dado novo (por exemplo `CASAS_LIMIAR_REGRA = 4`), para-se e
  avisa-se o dono antes de mexer.
- **O painel da árvore ganha largura proporcional** às folhas (80 por folha, mínimo 1280) dentro de um contêiner com
  rolagem horizontal, e leva o caminho em foco para a tela. A lógica pura (`caminho.js`) não muda.
- **Pesos: análise fora do repositório** (script no scratchpad, como a do relatório). Só muda `PESO_CLASSES_AJUSTE` se a
  regra da spec (ganho > 0,005 na validação e na dobra interna) for cumprida.
- **Referência congelada:** cópia de `data/gold/`, `data/modelo/` e `web/dados/replay.json` antes do piso (ignoradas
  pelo git), para o "antes × depois" do relatório e para o teste de reversão.

## Grafo de dependências

```
P1 cópia de referência (gold, modelo, replay)
 └─ P2 linha 3 com piso + checagens do Gold      ── reversão: piso None = Gold de antes; piso 30: X idêntico
     └─ P3 `arvore` + `ajuste` com o rótulo novo ── números reais, tamanho das árvores
         ├─ P4 varredura de pesos (análise)
         └─ P5 `replay` com os dados novos
             └─ P6 painel da árvore para 29 / 40 folhas
                 └─ P7 relatório (seção 8) + análise de robustez
                     └─ P8 AGENTS.md, specs, READMEs, memória
```

A cadeia é sequencial: cada passo lê a saída do anterior. P4 e P5 podem andar juntas depois de P3, mas P5 precisa
do peso final (se P4 trocá-lo, `ajuste` e `replay` são refeitos).

## Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| O refatoramento da linha 3 muda outra coisa sem querer | Alto | P2 roda primeiro com o piso em `None` e compara com a cópia de P1 (tem de ser idêntico), só depois liga o 30 |
| O Gold refeito muda alguma coluna do X | Alto | P2 compara `features_B.parquet` novo com a cópia, coluna a coluna |
| Os números em Spark diferem do protótipo (pandas) | Médio | Esperado e pequeno. Se a ajustada com peso sair muito fora de 0,66 a 0,71 de F1 ou a árvore da Tarefa 3 fora de 20 a 40 folhas, parar e investigar |
| `Regras.verificar` falha com o limiar de 4 casas numa árvore nova | Médio | É o aviso, não o erro: parar, mostrar ao dono e só então subir `CASAS_LIMIAR_REGRA` (precisa checar que `arvore` e `replay` continuam coerentes) |
| Alguma checagem do `replay` assume 16 folhas / 31 nós | Médio | P5 roda o `replay` antes de tocar na página; `grep` já não achou valor fixo, mas a execução decide |
| Painel ilegível com 40 folhas (3.200 unidades de largura) | Médio | P6 testa as duas árvores no navegador, com fluxos em foco de cantos diferentes, em largura de notebook e de tela grande; se não ficar legível, voltar ao dono com a opção de apertar a regra de escolha |
| O piso parecer escolhido pela validação | Médio | O relatório conta como o 30 foi escolhido (limite do RISCO) e mostra os vizinhos medidos no protótipo; nada é varrido no Gold final |
| O ganho sobre a persistência não ser maior | Baixo (já sabido) | Já está como ressalva da spec; o relatório mostra IC por fluxo e dobra interna reais, sem esconder |
| Alteração não commitada em `notebooks/02_*.ipynb` | Baixo | Não é desta spec; não entra em nada que o agente mexer. Nada é commitado sem o dono pedir |

## Verificação

Sem framework de testes: cada tarefa termina rodando o comando afetado, que para com `assert`.

- **Depois de P2:** o Gold passa nas duas configurações (piso `None` = idêntico ao antigo; piso 30 = X idêntico, só o Y
  muda) e imprime a tabela de destino das rebaixadas.
- **Depois de P3:** `arvore` e `ajuste` passam; o dono vê os números reais (checkpoint 1).
- **Depois de P6:** `replay` e página conferem (placar e matriz ao fim = CSVs) com as duas árvores no painel
  (checkpoint 2).
- **Depois de P8:** os 7 critérios de sucesso da spec marcados.

## Skills do catálogo

Nenhuma tarefa pede skill fora das instaladas. Em P6, a verificação visual usa a ferramenta de navegador embutida
(`servir` já está em `.claude/launch.json`), não uma skill.
