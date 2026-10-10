# Documentação do projeto

Este diretório reúne a documentação sobre os dados, as decisões do grupo e as orientações acadêmicas do projeto.

## Pastas

### [`../data`](../data/README.md)

Documenta a fonte e o recorte dos dados usados pelo projeto. O README registra a tabela do RIPE Atlas BigQuery, os IDs das probes e os destinos selecionados. Em [`../data`](../data/docs/query.md) estão a história da exploração e as consultas SQL; o documento [`dataset-fonte-atlas.md`](../data/docs/dataset-fonte-atlas.md) registra a evolução da fonte de dados.

### [`memorando/`](memorando/memorando_de_decisao_grupo16.md)

Guarda o memorando de decisões do grupo, com o registro das escolhas e do encaminhamento do trabalho.

### [`projeto_preditor_redes/`](projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md)

Contém o passo a passo enviado pela professora para o projeto acadêmico, incluindo o RFC e o guia de coleta. A subpasta [`tarefas/`](projeto_preditor_redes/tarefas/Tarefa1_Coleta_Bruta.md) contém os diários das cinco etapas:

1. [Tarefa 1 — Coleta bruta](projeto_preditor_redes/tarefas/Tarefa1_Coleta_Bruta.md)
2. [Tarefa 2 — Baseline e rotulagem](projeto_preditor_redes/tarefas/Tarefa2_Baseline_e_Rotulagem.md)
3. [Tarefa 3 — Árvore inicial](projeto_preditor_redes/tarefas/Tarefa3_Arvore_Inicial.md)
4. [Tarefa 4 — Ajuste da árvore](projeto_preditor_redes/tarefas/Tarefa4_Ajuste_da_Arvore.md)
5. [Tarefa 5 — Árvore final](projeto_preditor_redes/tarefas/Tarefa5_Arvore_Final.md)

### [`relatorio_analise_arvore.md`](relatorio_analise_arvore.md)

Análise da árvore da Tarefa 3 (como está, vieses, testes de colunas, pesos e hiperparâmetros), a combinação escolhida para a Tarefa 4, o resultado real depois da implementação e o diagnóstico do teto dos dados. Desde 10/10/2026, a seção 8 mede o piso da
regra 3 (antes × depois, com IC por fluxo); as seções 1 a 7 valem para o rótulo anterior ao piso.

## Referências principais

- [Consultas BigQuery e histórico da seleção regional](../data/docs/query.md)
- [Evolução da fonte de dados](../data/docs/dataset-fonte-atlas.md)
- [Guia de coleta RIPE Atlas enviado pela professora](projeto_preditor_redes/Guia_Coleta_RIPE_Atlas.md)
- [RFC do preditor de degradação de rede](projeto_preditor_redes/RFC_Preditor_Degradacao_Rede.md)
- [Memorando de decisões do grupo 16](memorando/memorando_de_decisao_grupo16.md)
