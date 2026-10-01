# Tarefas: arquitetura medalhão

Plano: [`plan.md`](plan.md) · Spec: [`SPEC-medalhao.md`](../SPEC-medalhao.md)

Verificação padrão de toda tarefa (o projeto não tem testes nem linter):
`uv run python -c "import preditor.__main__"` e, havendo rede/credenciais, o comando indicado na tarefa.

---

## ✅ T1: Referência da saída atual e caminhos das camadas

**Descrição:** Antes de mudar qualquer lógica, rodar o pipeline atual e guardar a saída como referência. Depois
adicionar em `config.py` os caminhos `DADOS`, `BRONZE`, `SILVER`, `GOLD` (com comentário de origem), mantendo
`SAIDA` por enquanto.

**Critérios de aceite:**
- [ ] `docs/data/_referencia/` contém `baseline_por_fluxo.parquet`, `features_B.parquet` e
      `limites_por_regiao.csv` gerados pelo código atual nesta data
- [ ] O corte A/B e as contagens impressas pelo pipeline (fluxos, insuficientes, linhas de features) estão
      anotados no fim deste arquivo, em "Números de referência"
- [ ] `config.py` tem `BRONZE`, `SILVER`, `GOLD`; nada mais mudou de comportamento

**Verificação:**
- [ ] `uv run python -m preditor` termina sem erro (antes da cópia)
- [ ] `git status` não mostra `docs/data/_referencia/` (ignorada por `/docs/data/*`)

**Dependências:** nenhuma
**Arquivos:** `src/preditor/config.py`, `tasks/todo.md`
**Escopo:** pequeno

## ✅ T2: Camada Bronze e CLI por camada

**Descrição:** Criar `bronze/ingestao.py` com a leitura do BigQuery (movida de `Medicoes.ler_bigquery()`) e a
gravação fiel em `docs/data/bronze/atlas.parquet`. Dar ao `__main__.py` um argumento opcional de camada com
`argparse`. Nesta tarefa só `bronze` existe como camada isolada; sem argumento, roda o Bronze e depois o fluxo
de hoje, já lendo as medições a partir do Parquet do Bronze.

**Critérios de aceite:**
- [ ] `uv run python -m preditor bronze` grava `docs/data/bronze/atlas.parquet` com as mesmas colunas da
      tabela (incluindo `pings` aninhado)
- [ ] Checagem automática: número de linhas do Parquet = número de linhas lidas do BigQuery
- [ ] O tamanho do Bronze em disco é informado ao dono (risco "tabela grande demais")
- [ ] `uv run python -m preditor` continua gravando a mesma saída em `processed/`

**Verificação:**
- [ ] `uv run python -m preditor bronze`
- [ ] `uv run python -m preditor` imprime o mesmo corte A/B e as mesmas contagens de "Números de referência"

**Dependências:** T1
**Arquivos:** `src/preditor/bronze/__init__.py`, `src/preditor/bronze/ingestao.py`, `src/preditor/__main__.py`,
`src/preditor/normalizacao/medicao.py`
**Escopo:** médio

## Checkpoint A
- [ ] Bronze gravado; pipeline completo com os mesmos números de referência

---

## ✅ T3: Camada Silver lendo do Bronze

**Descrição:** Mover `normalizacao/medicao.py` para `silver/medicao.py`. A camada lê o Bronze do disco, aplica
`transformar()` e grava `docs/data/silver/medicoes.parquet`. Adicionar o comando `silver`, a mensagem de erro
quando o Bronze não existe e as checagens do Silver. O cálculo do X passa a ler o Silver do disco (ainda
gravando em `processed/`). Remover o `spark` sem uso de `Medicoes.__init__` (achado da revisão da T2).

**Critérios de aceite:**
- [ ] `uv run python -m preditor silver` roda sem rede e grava `docs/data/silver/medicoes.parquet`
- [ ] Sem `docs/data/bronze/`, o comando termina com mensagem mandando rodar `bronze` antes
- [ ] Checagens automáticas: nenhum `rtt <= 0`; `periodo` só `A` ou `B`; 82 `fluxo_id` distintos (81 do baseline + 1 fluxo só com Período B)
- [ ] `src/preditor/normalizacao/` não existe mais
- [ ] O corte A/B impresso é o mesmo da referência

**Verificação:**
- [ ] `uv run python -m preditor silver` com a rede desligada (ou sem credenciais)
- [ ] Renomear `docs/data/bronze` temporariamente e conferir a mensagem de erro

**Dependências:** T2
**Arquivos:** `src/preditor/silver/__init__.py`, `src/preditor/silver/medicao.py`, `src/preditor/__main__.py`,
`src/preditor/normalizacao/` (removida)
**Escopo:** médio

## ✅ T4: Camada Gold

**Descrição:** Mover `calculo_x/` e `calculo_y/` para dentro de `gold/` e ajustar os imports. O comando `gold`
lê o Silver do disco e grava `baseline_por_fluxo.parquet`, `features_B.parquet` e `limites_por_regiao.csv` em
`docs/data/gold/`. Remover `SAIDA` de `config.py`. Sem argumento, o `__main__` roda bronze → silver → gold.

**Critérios de aceite:**
- [ ] `uv run python -m preditor gold` roda sem rede e grava os três arquivos em `docs/data/gold/`
- [ ] Sem `docs/data/silver/`, o comando termina com mensagem mandando rodar `silver` antes
- [ ] Checagens automáticas: Período A não vaza para `features_B`; 81 fluxos no baseline, 2 com
      `baseline_insuficiente`
- [ ] `src/preditor/calculo_x/` e `src/preditor/calculo_y/` não existem mais na raiz do pacote
- [ ] Nenhuma referência a `config.SAIDA` ou a `processed` no código

**Verificação:**
- [ ] `uv run python -m preditor gold`
- [ ] `uv run python -m preditor` (as três camadas em sequência)
- [ ] `grep -rn "SAIDA\|processed\|preditor.calculo_\|normalizacao" src/` não retorna nada

**Dependências:** T3
**Arquivos:** `src/preditor/gold/__init__.py`, `src/preditor/gold/calculo_x/*` (movidos),
`src/preditor/gold/calculo_y/__init__.py` (movido), `src/preditor/__main__.py`, `src/preditor/config.py`
Desvio autorizado pelo dono: `src/preditor/spark.py` também mudou (`build_spark(com_bigquery)`: o conector do
BigQuery só é declarado no `bronze` e no pipeline completo, para `silver`/`gold` rodarem offline).
**Escopo:** médio (são movimentações; a lógica não muda)

## ✅ T5: Comparação do Gold com a referência

**Descrição:** Comparar `docs/data/gold/` com `docs/data/_referencia/` usando um script descartável (fora do
repositório): mesmas colunas, mesmo número de linhas e `exceptAll` vazio nos dois sentidos para o baseline e
para `features_B`; `diff` para o CSV.

**Critérios de aceite:**
- [ ] `baseline_por_fluxo`: esquema igual e `exceptAll` vazio nos dois sentidos
- [ ] `features_B`: esquema igual e `exceptAll` vazio nos dois sentidos
- [ ] `limites_por_regiao.csv` idêntico
- [ ] Se houver qualquer diferença: maior diferença absoluta por coluna relatada ao dono, sem aceitar
      tolerância por conta própria

**Verificação:**
- [ ] Saída do script de comparação colada no relatório da tarefa

**Dependências:** T4
**Arquivos:** nenhum do repositório
**Escopo:** pequeno

## Checkpoint B (revisão do dono)
- [ ] Gold idêntico à referência
- [ ] `silver` e `gold` rodam sem rede
- [ ] Dono revisa antes da limpeza

---

## ✅ T6: Documentação e limpeza

**Descrição:** Atualizar `AGENTS.md` e `README.md` (camadas, comandos, estrutura de pastas, regra de não
commitar dados). Apagar `docs/data/processed/`, `docs/data/_referencia/` e os `__pycache__` das pastas
removidas. Marcar os critérios de sucesso na spec.

**Critérios de aceite:**
- [ ] `AGENTS.md`: seções Commands, Conventions e Security rules falam de `bronze/`, `silver/`, `gold/`
- [ ] `README.md`: tabela de pastas e árvore de `src/preditor/` atualizadas
- [ ] `grep -rn "processed" AGENTS.md README.md docs/README.md docs/data/README.md src/` não retorna nada
- [ ] `docs/data/processed/` e `docs/data/_referencia/` apagadas (só depois do Checkpoint B aprovado)

**Verificação:**
- [ ] `uv run python -c "import preditor.__main__"`
- [ ] `uv run python -m preditor gold` ainda passa nas checagens

**Dependências:** T5 e aprovação do Checkpoint B
**Arquivos:** `AGENTS.md`, `README.md`, `SPEC-medalhao.md`
**Escopo:** pequeno

## Checkpoint final
- [ ] Todos os critérios de sucesso de `SPEC-medalhao.md` marcados
- [ ] Pronto para `/review`

---

## Números de referência

Saída do pipeline atual (`uv run python -m preditor`, sem alterar código), rodado em 30/09/2026 na T1.
A cópia em `docs/data/_referencia/` foi apagada na T6, depois de a T5 confirmar o Gold idêntico (código de origem: commit `505723e`).

- Corte A/B: `2026-09-22 14:10:03`
- Fluxos: 81 | com baseline: 79 | insuficientes: 2 (contagem do baseline; as medições têm 82 `fluxo_id`, contando o fluxo sem Período A)
- `baseline_insuficiente`: `7708|92.38.132.60|213834730` e `7708|92.38.132.60|213085266`
- Sem medições no Período A (fora do modelo): `7708|92.38.132.60|214331389`
- Linhas de features (B): 70670
- `limites_por_regiao.csv`: 6 linhas (BR→Brasil, América do Norte/US, Europa/DE, Europa/PT, Ásia/JP, Ásia/SG)
