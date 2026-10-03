# Relatório: como a árvore está hoje e a melhor combinação encontrada

Data: 02/10/2026. Análise exploratória para a Tarefa 4.

**Como foi feito.** Tudo foi medido só com os blocos de treino e validação; o teste continua fechado. Os testes
rodaram em scripts temporários, fora do repositório: nenhum arquivo de `src/`, `config.py` ou `data/` foi alterado.
As colunas novas foram calculadas em pandas a partir do `dataset_rotulado_B.parquet`, sem mexer no Gold.
Semente 16 em tudo.

## 1. Resumo

- A árvore oficial (F1 macro 0,7457) ganha da persistência (0,7221) por pouco, porque **quase repete o estado
  atual**: a previsão é igual ao `status_atual` em 92,6 % das linhas.
- Trocar só hiperparâmetros ou só o peso das classes **não melhora** de forma mensurável (+0,0015, dentro do ruído).
- O que melhora são **duas colunas novas de histórico do `z_robusto`** (`min5_z` e `media5_z`) **junto com o peso
  de classes** {OK 1, RISCO 2, FALHA 1,5}.
- **Melhor combinação legível (recomendada):** 8 colunas + `min5_z` + `media5_z`, Gini, `max_depth` 4,
  `min_samples_leaf` 50, com o peso acima. F1 macro **0,7600** (+0,0145 sobre a oficial, IC 95 % de +0,007 a +0,022),
  com as mesmas 16 folhas.
- **Melhor combinação em número:** as mesmas colunas + `incl5_z`, `max_depth` 6, `min_samples_leaf` 100, mesmo peso.
  F1 macro **0,7648** (+0,0194, IC 95 % de +0,010 a +0,029), com 43 folhas.
- Limite que continua: nenhuma combinação antecipa bem o **início** de uma falha (OK → FALHA: no máximo 7 % de acerto).

## 2. Como a árvore está hoje

Árvore oficial: Gini, `max_depth` 4, `min_samples_leaf` 50, 16 folhas, sem peso de classe, 8 colunas.
Treino com 34.661 linhas, validação com 13.490.

| Métrica (validação) | Persistência | Árvore oficial |
|---|---|---|
| F1 macro | 0,7221 | 0,7457 |
| Acurácia | 0,8064 | 0,8290 |
| Recall OK | 0,868 | 0,919 |
| Recall RISCO | 0,488 | 0,490 |
| Recall FALHA | 0,809 | 0,779 |

A diferença para a persistência é real: +0,023, IC 95 % de +0,011 a +0,033 (bootstrap por fluxo).

### 2.1 Ela quase repete o agora

| Situação na validação | N | Acerto da árvore | Acerto da persistência |
|---|---|---|---|
| Futuro igual ao agora | 10.878 | 97,2 % | 100 % |
| Futuro diferente do agora | 2.612 | 23,4 % | 0 % |

Acerto por transição (agora → futuro): OK → FALHA 1,8 % (491 casos), OK → RISCO 13,1 % (595), FALHA → OK 16,4 % (488),
RISCO → OK 62,7 % (587).

### 2.2 Vieses encontrados

- **Sobreajuste: não há.** F1 do treino 0,729, da validação 0,746; a pureza das folhas é quase igual nos dois blocos.
- **Viés para OK (leve).** Previstos 8.734 OK contra 8.145 reais; 1.317 RISCO contra 1.609; 3.439 FALHA contra 3.736.
- **Viés por região (o mais forte).**

| Região | Linhas | F1 árvore | F1 persistência | Recall FALHA | Recall RISCO |
|---|---|---|---|---|---|
| Ásia | 4.438 | 0,788 | 0,756 | 0,790 | 0,619 |
| Europa | 4.433 | 0,748 | 0,746 | 0,887 | 0,353 |
| América do Norte | 2.221 | 0,632 | 0,624 | 0,720 | 0,222 |
| Brasil | 2.398 | 0,479 | 0,493 | 0,484 | 0,037 |

  No Brasil a árvore perde da persistência.
- **Por fluxo.** A acurácia vai de 0,49 a 1,00 (mediana 0,855); 10 dos 79 fluxos concentram 30 % dos erros. A árvore
  ganha da persistência em 56 fluxos e perde em 8.
- **Blocos diferentes.** FALHA é 22,2 % do treino e 27,7 % da validação; os fluxos com mais de 50 % de FALHA passam
  de 6 para 14. A validação cobre só 12 horas (das 20 h às 8 h).
- **Alvo dominado pela regra 3.** Das 3.736 FALHAs futuras da validação, 3.480 vêm da regra 3 (`z_robusto` ≥ 3,5).
  A árvore acerta 81 % delas, 31 % das de regra 1 e 41 % das de regra 4.
- **Colunas sem uso.** `perda_pct`, `timeout_atual` e `n5_timeout` têm importância 0. `z_robusto` tem 77 % e
  `n5_moderado`, 17 %. Tirar as três não muda nenhum resultado.

## 3. Testes

Cada combinação foi medida de duas formas, para não escolher por sorte:

- **Validação:** `fit` no treino inteiro, medida na validação (o protocolo oficial).
- **Dobra interna:** `fit` nos primeiros 60 % do treino (por tempo, com folga de 3 medições), medida nos 40 % finais.
  Persistência nessa dobra: 0,7141.

### 3.1 Só hiperparâmetros e peso (8 colunas)

| Combinação | Folhas | F1 validação | F1 interna | Recall RISCO | Recall FALHA |
|---|---|---|---|---|---|
| Oficial (Gini 4 / 50, sem peso) | 16 | 0,7457 | 0,7246 | 0,490 | 0,779 |
| Gini 4 / 50, peso {RISCO 2, FALHA 1,5} | 16 | 0,7468 | 0,7321 | 0,588 | 0,777 |
| Gini 2 / 50, `balanced` | 4 | 0,7483 | 0,7335 | 0,547 | 0,774 |
| Gini 6 / 200, peso {RISCO 2, FALHA 1,5} | 44 | 0,7548 | 0,7276 | 0,572 | 0,771 |
| Entropia 10 / 100, sem peso | 161 | 0,7519 | 0,7254 | 0,503 | 0,778 |
| Sem limite (folha mínima 1) | 6.828 | 0,6490 | — | — | — |

O peso sobe o recall de RISCO (0,49 → 0,59) sem perder FALHA, mas o F1 macro não muda de forma mensurável:
+0,0015, IC 95 % de −0,005 a +0,008. Poda por `ccp_alpha` (≈ 0,00016) chega a 0,7506 com 74 folhas, na mesma faixa.

### 3.2 Colunas de mudança

Doze colunas novas, todas calculadas só com o passado e o presente do mesmo fluxo (janela pelas últimas medições,
como as `n5_` do Gold). Cada uma somada às 8, com Gini 4 / 50 e sem peso:

| Coluna somada | O que é | F1 validação | F1 interna | Acerto quando o futuro muda |
|---|---|---|---|---|
| (nenhuma: oficial) | | 0,7457 | 0,7246 | 23,4 % |
| `media5_z` | média do `z_robusto` nas últimas 5 | 0,7546 | 0,7351 | 29,9 % |
| `n20_z35` | quantas das últimas 20 têm z ≥ 3,5 | 0,7490 | 0,7424 | 31,5 % |
| `n10_z35` | idem, últimas 10 | 0,7489 | 0,7420 | 33,8 % |
| `d1_z` | z de agora − z anterior | 0,7459 | 0,7402 | 31,9 % |
| `min5_z` | menor z das últimas 5 | 0,7438 | 0,7434 | 35,2 % |
| `mediana10_z` | mediana do z nas últimas 10 | 0,7432 | 0,7436 | 34,9 % |
| `n5_z35` | quantas das últimas 5 têm z ≥ 3,5 | 0,7421 | 0,7451 | 32,7 % |
| `max5_z` | maior z das últimas 5 | 0,7424 | 0,7251 | 23,5 % |
| `d3_z` | z de agora − z de 3 atrás | 0,7393 | 0,7338 | 33,5 % |
| `d1_aumento` | variação do `aumento_pct` | 0,7392 | 0,7130 | 24,4 % |
| `desvio5_z` | desvio padrão do z nas últimas 5 | 0,7358 | 0,7080 | 23,8 % |
| `incl5_z` | inclinação do z nas últimas 5 | 0,7317 | 0,7126 | 32,5 % |
| todas as 12 | | 0,7436 | 0,7429 | 36,7 % |

Uma seleção para a frente (soma uma coluna por vez enquanto a média das duas medidas sobe) escolheu, nesta ordem:
`min5_z`, `media5_z`, `incl5_z`. Com profundidade 4 a `incl5_z` não é usada (importância 0).

As 5 colunas que já existem no Gold e estão fora (`latencia_relativa`, `tendencia`, `persistencia`, `moderado`,
`desviado`) não ajudam: de 0,7357 a 0,7470.

### 3.3 Grade completa

1.344 combinações: 6 conjuntos de colunas × Gini / entropia × `max_depth` {2, 3, 4, 5, 6, 8, 10} ×
`min_samples_leaf` {50, 100, 200, 500} × 4 pesos.

| Conjunto de colunas | F1 validação (média / máximo) | F1 interna (média / máximo) |
|---|---|---|
| 8 (oficial) | 0,7391 / 0,7548 | 0,7214 / 0,7419 |
| 8 + `n10_z35` | 0,7439 / 0,7616 | 0,7331 / 0,7527 |
| 8 + `media5_z` + `n10_z35` | 0,7437 / 0,7632 | 0,7334 / 0,7503 |
| 8 + as 12 novas | 0,7448 / 0,7638 | 0,7363 / 0,7584 |
| 8 + `min5_z` + `media5_z` + `incl5_z` | 0,7503 / 0,7648 | 0,7410 / 0,7598 |

- **Peso:** {RISCO 2, FALHA 1,5} tem a melhor média nas duas medidas; `balanced` tem a pior média de F1.
- **Critério:** Gini e entropia empatam (0,7445 contra 0,7425 na média). Não há motivo para trocar.
- A correlação entre as duas medidas, nas 1.344 combinações, é 0,65: o que vai bem numa tende a ir bem na outra.

## 4. Finalistas

| | A: oficial | B: só peso | C: recomendada | F: melhor número |
|---|---|---|---|---|
| Colunas | 8 | 8 | 8 + `min5_z` + `media5_z` | C + `incl5_z` |
| `max_depth` / `min_samples_leaf` | 4 / 50 | 4 / 50 | 4 / 50 | 6 / 100 |
| Peso {RISCO 2, FALHA 1,5} | não | sim | sim | sim |
| Folhas | 16 | 16 | 16 | 43 |
| F1 macro validação | 0,7457 | 0,7468 | **0,7600** | **0,7648** |
| F1 macro dobra interna | 0,7246 | 0,7321 | 0,7484 | 0,7531 |
| F1 macro treino | 0,7293 | 0,7257 | 0,7436 | 0,7552 |
| Acurácia | 0,829 | 0,819 | 0,836 | 0,840 |
| Recall OK | 0,919 | 0,884 | 0,927 | 0,923 |
| Recall RISCO | 0,490 | 0,588 | 0,564 | 0,566 |
| Recall FALHA | 0,779 | 0,777 | 0,754 | 0,779 |
| Precisão RISCO | 0,599 | 0,524 | 0,562 | 0,560 |
| Precisão FALHA | 0,846 | 0,838 | 0,910 | 0,903 |
| Acerto quando o futuro muda | 23,4 % | 22,2 % | 33,3 % | 34,3 % |
| Igual à persistência | 92,6 % | 91,9 % | 88,9 % | 88,9 % |
| F1 Ásia | 0,788 | 0,798 | 0,800 | 0,801 |
| F1 Europa | 0,748 | 0,751 | 0,753 | 0,769 |
| F1 América do Norte | 0,632 | 0,654 | 0,652 | 0,645 |
| F1 Brasil (persistência: 0,493) | 0,479 | 0,477 | 0,484 | 0,538 |
| Diferença para a oficial (IC 95 %) | — | +0,0015 (−0,005 a +0,008) | +0,0145 (+0,007 a +0,022) | +0,0194 (+0,010 a +0,029) |
| Diferença para a persistência (IC 95 %) | +0,023 (+0,011 a +0,033) | +0,025 (+0,013 a +0,034) | +0,038 (+0,026 a +0,049) | +0,043 (+0,032 a +0,053) |

As colunas novas sem o peso (8 + 3, Gini 4 / 50) dão 0,7425: não ganham da oficial. É a soma das duas mudanças que
funciona.

Matriz de confusão da recomendada (C), na validação (linha = real, coluna = previsto):

| | OK | RISCO | FALHA |
|---|---|---|---|
| OK | 7.548 | 416 | 181 |
| RISCO | 603 | 908 | 98 |
| FALHA | 627 | 291 | 2.818 |

### De onde vem o ganho

Na combinação C, `min5_z` passa a ser a raiz da árvore (75 % da importância) e `n5_moderado` fica com 19 %.
`min5_z` alto quer dizer que o z ficou alto nas 5 últimas medições: degradação sustentada, e não um pico isolado.

| Transição (agora → futuro) | A: oficial | C: recomendada | F |
|---|---|---|---|
| FALHA → OK (488 casos) | 16,4 % | 58,0 % | 57,2 % |
| OK → RISCO (595) | 13,1 % | 21,9 % | 24,4 % |
| RISCO → OK (587) | 62,7 % | 53,3 % | 53,3 % |
| OK → FALHA (491) | 1,8 % | 0,6 % | 7,3 % |

A melhora é quase toda em reconhecer que um pico isolado volta ao normal. Antecipar o início de uma falha continua
fora do alcance dessas colunas.

## 5. Recomendação

1. **Adotar a combinação C** como candidata da Tarefa 4: mesma estrutura da oficial (Gini, 4 / 50, 16 folhas), o que
   mantém as regras legíveis e deixa a comparação limpa. Só mudam duas colunas e o peso.
2. **Guardar a F como alternativa** se a prioridade for o número: +0,005 sobre a C e é a única que passa a
   persistência no Brasil, ao custo de 43 folhas.
3. **Reportar junto do F1 macro** o acerto quando o futuro muda e o F1 por região: são as duas medidas que mostram
   o que o F1 esconde.
4. **Não gastar tempo** com entropia, `min_samples_leaf` abaixo de 50, `balanced` ou com as 5 colunas extras do Gold.

## 6. Ressalvas

- **A escolha usou a validação.** Colunas, peso e hiperparâmetros foram escolhidos olhando a mesma validação que
  mede o resultado, então 0,7600 e 0,7648 são otimistas. A dobra interna aponta na mesma direção (+0,024 e +0,029
  sobre a oficial), o que dá confiança no sentido da melhora, não no valor exato. O número honesto só sai no teste
  da Tarefa 5.
- **Diferenças menores que 0,01** entre combinações estão dentro do ruído: o IC 95 % da própria oficial é 0,70 a 0,78.
- **As colunas novas foram prototipadas em pandas**, com janela pelas últimas linhas do fluxo, sem conferir o
  intervalo de tempo entre elas. Para valer, precisam entrar no Gold (`calculo_x`), com as mesmas regras de janela
  das `n5_`, e na lista `COLUNAS_ARVORE`. Os valores podem mudar um pouco.
- **Decisões que ficam com o dono:** incluir colunas fora da lista do diário da Tarefa 3; usar peso de classe (a
  decisão de 01/10 deixou o balanceamento para a Tarefa 4); e se 43 folhas ainda contam como árvore explicável.
- **O limite do alvo continua.** 93 % das FALHAs futuras vêm da regra 3, e o viés por região diminui pouco na C.

## 7. Depois da implementação: resultado real e teto (02/10/2026)

As duas colunas entraram no Gold e a árvore ajustada tem comando próprio (`uv run python -m preditor ajuste`, spec em
`SPEC-ajuste-arvore.md`). O cálculo em Spark reproduz o protótipo, e os números se repetiram:

| Modelo (validação) | Escolhida | Folhas | F1 macro | Recall FALHA | Recall RISCO | Acerto quando o futuro muda |
|---|---|---|---|---|---|---|
| Persistência | | | 0,7221 | 0,8092 | 0,4879 | 0,0 % |
| Árvore da Tarefa 3 | Gini 4 / 50 | 16 | 0,7457 | 0,7786 | 0,4904 | 23,4 % |
| Ajustada sem peso | Gini 2 / 500 | 4 | 0,7553 | 0,7224 | 0,6010 | 35,9 % |
| Ajustada com peso (adotada) | Gini 4 / 100 | 16 | 0,7600 | 0,7543 | 0,5643 | 33,3 % |

### 7.1 O teto: o limite é dos dados, não da árvore

Para saber se ainda há o que ajustar, modelos bem mais fortes foram treinados nas mesmas linhas, só como diagnóstico
(scripts temporários; nenhum deles entra no projeto, que continua sendo uma árvore de decisão):

| Modelo (validação) | F1 macro | Acerto em OK → FALHA | F1 Brasil |
|---|---|---|---|
| Persistência | 0,7221 | 0,0 % | 0,493 |
| Árvore da Tarefa 3 | 0,7457 | 1,8 % | 0,479 |
| Árvore ajustada (16 folhas) | 0,7600 | 0,6 % | 0,484 |
| Boosting (300 árvores), as mesmas 10 colunas | 0,7577 | 8,4 % | 0,515 |
| Floresta (300 árvores), 20 colunas | 0,7594 | 9,0 % | 0,519 |
| Boosting, 20 colunas | 0,7662 | 9,8 % | 0,527 |
| Boosting, 20 colunas, peso balanceado | 0,7612 | 13,4 % | 0,572 |
| Boosting, 20 colunas + `rtt` + taxa de FALHA e RISCO de cada fluxo no treino | 0,7623 | 10,0 % | 0,550 |

As 20 colunas são as 8 da Tarefa 3 mais as 12 da seção 3.2. A última linha dá ao modelo a identidade do fluxo e o
RTT absoluto, que o projeto proíbe: está ali só para mostrar que nem isso passa de 0,77.

A árvore de 16 folhas empata com um boosting de 300 árvores. Três medidas explicam o porquê:

- **A falha não avisa.** Entre as 8.156 linhas da validação que estão OK agora, 6,0 % viram FALHA em 12 minutos. O
  `z_robusto` mediano de agora é −0,23 nas que viram FALHA e −0,30 nas que continuam OK; o `min5_z` mediano é −0,70
  e −0,73. Não há sinal anterior para nenhum modelo aprender.
- **A maioria das falhas é um pico de uma medição.** Dos 2.436 episódios de FALHA em treino e validação (FALHAs
  seguidas do mesmo fluxo), 68,3 % duram uma medição e 82,6 % duram até duas. A regra 3 (`z_robusto` ≥ 3,5, sem piso
  em ms nem em %) gera 93 % das FALHAs futuras da validação.
- **O dado é só ping.** RTT, jitter e perda de um fluxo por vez, a cada 4 minutos. Sem traceroute, sem carga da rede
  e sem cruzar fluxos vizinhos, que é onde um precursor poderia aparecer.

### 7.2 Leitura do ganho e da queda do recall de FALHA

- O ganho vem de reconhecer o pico isolado: quando o agora é FALHA e o futuro é OK (488 linhas), o acerto vai de
  16,4 % para 58,0 %. `min5_z` vira a raiz da árvore, com 75 % da importância.
- O recall de FALHA cai de 0,779 para 0,754, e a precisão de FALHA sobe de 0,846 para 0,910. A árvore deixa de chamar
  de FALHA os picos que voltam a OK: dá menos alarmes, e os que dá são mais confiáveis.
- Antecipar o início de uma falha a 12 minutos (OK → FALHA) não é possível com estas medições: nenhum modelo testado
  passa de 13,4 %.
- O viés por região diminui pouco. O Brasil continua abaixo da persistência na árvore ajustada (0,484 contra 0,493).

### 7.3 Pendências para a revisão com a professora

1. **Peso de classe.** Não está na lista de ajustes permitidos do diário da Tarefa 4. As duas variantes estão medidas;
   se ela vetar, a ajustada passa a ser a sem peso (0,7553, 4 folhas) trocando `MODELO_AJUSTADA` em `config.py`.
2. **Regra 3 do rótulo.** Com 68 % dos episódios de FALHA durando uma medição, vale perguntar se a Tarefa 5 pode dar
   um piso à regra (por exemplo, `aumento_pct` ≥ 30 %) ou exigir duas medições seguidas. Até lá, vale a decisão do
   dono de seguir a regra dela, e isto fica como limitação conhecida.

O que não se recomenda: trocar de algoritmo (o diário proíbe e o diagnóstico mostra que não ajuda), usar árvores de
43 ou 187 folhas (+0,004, dentro do ruído), encurtar o horizonte de 12 minutos (muda a pergunta do projeto) ou abrir
o teste antes da Tarefa 5.
