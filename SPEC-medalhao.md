# Spec: Arquitetura medalhão (Bronze / Silver / Gold)

Status: **aprovada pelo dono em 30/09/2026**.

## Objetivo

Separar o pipeline em três camadas de dados gravadas em disco, no padrão medalhão:

| Camada | O que guarda | Quem produz | Formato / local |
|---|---|---|---|
| **Bronze** | Cópia fiel da tabela `atlas-ripe-509700.atlasRipe.atlas` (mesmas colunas, `pings` ainda aninhado, sem filtro nem cálculo) | `bronze/` | `data/bronze/atlas.parquet` |
| **Silver** | Medições normalizadas: uma linha por medição com `fluxo_id`, metadados de rota, `t`, `rtt`, `jitter`, `perda_pct`, `timeout_atual`, `periodo` | `silver/` (hoje `normalizacao/`) | `data/silver/medicoes.parquet` |
| **Gold** | Tabelas prontas para o modelo: `baseline_por_fluxo`, `features_B`, o Y quando existir (`calculo_y`), `limites_por_regiao.csv` | `gold/` (hoje `calculo_x/` e `calculo_y/`) | `data/gold/…` |

**Por quê:**

- O BigQuery passa a ser lido **uma vez** (Bronze). Silver e Gold rodam offline, sem rede nem credenciais, o que deixa
  a iteração no cálculo do Y e na árvore mais rápida e mais barata.
- Cada camada pode ser inspecionada e verificada sozinha, o que ajuda quem está aprendendo PySpark.
- O dataset de treino (Gold) fica separado das medições (Silver), deixando claro o que é dado e o que é feature/rótulo.

**Não muda:** as fórmulas (RFC §8.2 a §8.4), o corte de 108 h, a definição de RTT válido, o `fluxo_id`, as colunas e
os valores das saídas atuais. É uma refatoração: os números do Gold precisam bater com os de hoje.

**Fora do escopo:** implementar o cálculo do Y ou a árvore; gravar camadas no BigQuery; os notebooks `01`–`03`
(continuam usando a API do Atlas).

## Stack

Sem mudança: Python 3.11 + `uv`, PySpark 3.5 local, conector Spark do BigQuery (só no Bronze), Java 17. Nenhuma
dependência nova.

## Comandos

```bash
uv sync
uv run python -m preditor            # roda bronze → silver → gold
uv run python -m preditor bronze     # lê o BigQuery e grava data/bronze/ (precisa de rede e gcloud)
uv run python -m preditor silver     # lê bronze do disco, grava data/silver/
uv run python -m preditor gold       # lê silver do disco, grava data/gold/
uv run python -c "import preditor.__main__"   # verificação mínima sem rede
```

Rodar `silver` ou `gold` sem a camada anterior no disco termina com uma mensagem clara dizendo qual comando rodar
antes. Não recai silenciosamente no BigQuery.

## Estrutura do projeto

As camadas ficam por fora e as etapas por dentro:

```
src/preditor/
  __main__.py          → CLI: escolhe a camada (ou todas), orquestra, roda as checagens
  config.py            → parâmetros + caminhos de cada camada (BRONZE, SILVER, GOLD)
  spark.py             → sessão Spark (inalterado)
  bronze/
    ingestao.py        → lê a tabela do BigQuery e grava como está
  silver/
    medicao.py         → hoje normalizacao/medicao.py (lê do Bronze em vez do BigQuery)
  gold/
    calculo_x/         → baseline.py, features.py, relatorio_regiao.py (movidos de calculo_x/)
    calculo_y/         → placeholder atual (movido de calculo_y/)
data/
  bronze/ silver/ gold/  → saídas (já ignoradas pelo git via /data/*)
  processed/             → removida (substituída pelas três camadas)
```

A separação `ler_bigquery()` / `transformar()` que já existe em `Medicoes` vira a fronteira Bronze/Silver:
`ler_bigquery()` vai para `bronze/`, e `transformar()` passa a receber o DataFrame lido do Parquet do Bronze.

## Estilo de código

Segue o `AGENTS.md`: nomes e comentários em português, números e caminhos em `config.py` com a origem comentada,
transformações legíveis e explicadas. Exemplo do tamanho de mudança esperado:

```python
# config.py
DADOS = Path(__file__).resolve().parents[2] / "data"
BRONZE = DADOS / "bronze"  # cópia fiel do BigQuery (medalhão, SPEC-medalhao.md)
SILVER = DADOS / "silver"  # uma linha por medição
GOLD = DADOS / "gold"      # baseline, features e rótulo: o que o modelo consome
```

## Estratégia de testes

Não há framework de testes no projeto (e esta spec não adiciona um). A verificação é:

1. **Checagens automáticas por camada**, rodadas pelo `__main__` ao fim de cada camada:
   - Bronze: número de linhas igual ao `COUNT(*)` da tabela no BigQuery; mesmas colunas.
   - Silver: nenhum `rtt <= 0`; todo `periodo` é `A` ou `B`; 82 `fluxo_id` distintos (81 do baseline + 1 fluxo só com Período B).
   - Gold: o Período A não vaza para `features_B` (checagem que já existe); 81 fluxos no baseline, 2 com
     `baseline_insuficiente`.
2. **Comparação com a saída atual** (feita uma vez, na migração): antes de mudar o código, guardar uma cópia de
   `data/processed/`. Depois comparar `baseline_por_fluxo` e `features_B` do Gold com essa cópia. Tem de haver
   as mesmas linhas, as mesmas colunas e os mesmos valores (`exceptAll` vazio nos dois sentidos).

## Limites

- **Sempre:** manter as fórmulas e os números idênticos; gravar só em `data/{bronze,silver,gold}/`; atualizar
  `AGENTS.md` e `README.md` com os novos comandos e pastas.
- **Perguntar antes:** adicionar dependências ou framework de testes; mudar colunas ou valores de qualquer saída;
  gravar qualquer coisa no BigQuery; apagar `data/processed/` antes de a comparação passar.
- **Nunca:** commitar dados de nenhuma camada; versionar credenciais; mexer nos notebooks `01`–`03`; usar
  região/país como feature.

## Critérios de sucesso

- [x] `uv run python -m preditor bronze` grava `data/bronze/atlas.parquet` com o mesmo número de linhas da
  tabela no BigQuery.
- [x] `uv run python -m preditor silver` e `… gold` rodam **sem rede** (com o Bronze já no disco).
- [x] Rodar `silver` sem o Bronze no disco falha com uma mensagem que manda rodar `bronze` antes, e o mesmo vale
      para `gold` sem o Silver.
- [x] `uv run python -m preditor` (sem argumento) roda as três camadas em sequência e passa em todas as checagens.
- [x] `baseline_por_fluxo` e `features_B` do Gold são idênticos aos de `data/processed/` de antes da mudança.
- [x] O código está em `src/preditor/{bronze,silver,gold}/`; `normalizacao/` e as pastas `calculo_*` da raiz não
      existem mais.
- [x] `AGENTS.md` e `README.md` descrevem as camadas e os comandos novos; nenhuma referência a
      `data/processed/` sobra no código ou na documentação.

## Decisões fechadas

1. **Bronze completo:** copia a tabela inteira como está, sem filtrar probes nem destinos.
2. **Relatório por região no Gold:** `limites_por_regiao.csv` fica em `data/gold/`.
