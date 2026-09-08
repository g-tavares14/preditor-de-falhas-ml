# Organização

Ler este arquivo quando a tarefa cria pasta, classe, Protocol ou camada. Não
copiar isto para o `AGENTS.md` da raiz.

## Pastas

Pasta nova só com dois módulos que mudam pelo mesmo motivo. Um arquivo por pasta
é recusa.

Fluxo de dados: arquivos no pacote (`extract.py`, `transform.py`, `load.py`) só os
que o fluxo usar. Sem pasta `etl/` com um arquivo. Pipeline vira classe só com
estado entre etapas (conexão aberta, workbook aberto). Caso contrário, função.

## Tipos (nessa ordem)

1. Função — operação dados → dados ou dados → efeito.
2. `dataclass` — dado + invariante simples.
3. Classe — estado compartilhado entre operações, ou invariante no objeto.
4. Protocol / ABC — duas implementações reais, ou teste que substitui I/O.

## SOLID com parada

- **S:** uma razão de mudança por módulo/classe. Não é um arquivo por função.
- **O:** novo módulo quando `if`/`match` de tipo se repetir. Sem gancho futuro.
- **L:** ignore se não houver herança.
- **I:** sem protocolo de um implementador.
- **D:** `Path`, file-like ou função já é injeção. Sem container no fluxo 1.

## Over-engineering (recusar)

- ABC/Protocol com uma implementação
- Pasta com um arquivo
- Camada que só chama a de baixo
- Factory / Strategy / Singleton / Repository / Event / Plugin sem o problema de hoje
- Config genérica antes do segundo chamador

## Declaração no incremento que mexe em estrutura

- Pastas criadas e por quê.
- Tipos novos; se houve classe, o motivo.
- Se houve Protocol/ABC: qual o segundo uso.
- Gates do `AGENTS.md` e o resultado.
- Fluxo em um parágrafo: entrada → regra → saída ou erro.
