# Relatório: como a árvore está hoje e a melhor combinação encontrada

Data: 02/10/2026. Análise exploratória para a Tarefa 4.

**Como foi feito.** Tudo foi medido só com os blocos de treino e validação; o teste continua fechado. Os testes
rodaram em scripts temporários, fora do repositório: nenhum arquivo de `src/`, `config.py` ou `data/` foi alterado.
As colunas novas foram calculadas em pandas a partir do `dataset_rotulado_B.parquet`, sem mexer no Gold.
Semente 16 em tudo.

> **Nota (10/10/2026).** As seções 1 a 7 valem para o rótulo anterior ao piso da regra 3 (commit `055c422`), em que a
> regra 3 era só `z_robusto` ≥ 3,5. Não foram reescritas. A seção 8 mede o rótulo com o piso (`aumento_pct` ≥ 30 %),
> antes × depois. Os números das seções 1 a 7 não se comparam com os da seção 8: o F1 não se compara entre os dois
> rótulos (ver 8.3).

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

## 8. Piso na regra 3: antes × depois (10/10/2026)

**Escopo.** A regra 3 passou a exigir `aumento_pct` ≥ 30 % além de `z_robusto` ≥ 3,5 (`SPEC-piso-regra3.md`). "Antes" é o
rótulo do commit `055c422` (`data/gold_antes_do_piso/`, árvores em `data/modelo_antes_do_piso/`). "Depois" é o rótulo
atual (`data/gold/`, árvores em `data/modelo/`). O X é o mesmo nos dois: a análise confere todas as colunas pela chave
`(fluxo_id, t)`. O teste continua fechado: só o N aparece.

**Fontes.** Todo número desta seção está em `data/analise_piso_regra3/numeros_secao8.csv`, com a fonte de cada um: o
script `robustez_piso.py` (IC, dobra, pares, contagens) ou um CSV de `data/modelo*/`. O rótulo final, com o piso em
`None` e em 30, foi conferido em `conferir_rotulo_piso.py` (log ao lado). Os dois pontos da seção 7.3 têm agora uma
decisão: o piso foi aplicado (8.2) e o peso de classe foi mantido (8.6). A professora ainda não revisou o registro no
diário da Tarefa 4, que segue com o dono.

### 8.1 O que o piso muda no rótulo

A regra 3 tinha 16.305 medições. Com o piso, 1.935 continuam nela. As outras 14.370 (88,1 %) saem:

| Destino | Medições | Classe nova |
|---|---|---|
| Regra 4 | 5 | FALHA |
| Regra 5 | 2.929 | RISCO |
| Regra 6 | 11.436 | OK |

Entre as 14.370, 9.251 têm `z_robusto` ≥ 8. A mediana do z delas é 14,65 e a do `aumento_pct` é 4,2 %. Uma medição com
z muito alto e aumento pequeno passa a ser OK, enquanto uma com z entre 2 e 3,5 ainda pode contar como RISCO. A ordem
parece estranha, mas é o que o piso pretende: um z alto com aumento pequeno vem de um MAD pequeno, em fluxos muito
estáveis, em que uma variação de poucos décimos de ms já é um desvio extremo. A alternativa de tratar essas medições
como moderadas foi descartada antes desta medição (`SPEC-piso-regra3.md`); seus números não estão salvos e não são usados
aqui.

A tabela mostra a classe do alvo (`status_futuro`) nas linhas que entram no modelo: treino e validação, depois de tirar
o futuro nulo e a folga. São 48.151 linhas nos dois rótulos (34.661 de treino e 13.490 de validação).

| Classe do alvo | Antes | Depois |
|---|---|---|
| OK | 62,3 % | 76,8 % |
| RISCO | 13,9 % | 17,8 % |
| FALHA | 23,8 % | 5,4 % |

Na validação, FALHA cai de 3.736 para 592 linhas.

### 8.2 De onde vem o 30

O 30 é o limite de RISCO por aumento que a própria tabela da RFC já usa: a linha 5 define RISCO com
`30 ≤ aumento_pct ≤ 80` (RFC §8.4; `AUMENTO_RISCO_PCT` em `config.py`). Com o piso, uma FALHA por z não é menos severa
que o RISCO por aumento: a regra 3 passa a exigir o mesmo aumento mínimo que a tabela já exige para o RISCO. O valor vem
da tabela, e não de uma busca.

A RFC permite ajustar limiares na validação (RFC §13, pergunta 2). Esse caminho não foi usado: nenhum valor de piso foi
varrido no rótulo final. Outros valores de piso foram medidos no protótipo de 09/10, mas esses resultados não estão
salvos no repositório e não foram refeitos; este relatório não os usa. Se a professora quiser a sensibilidade ao valor
do piso, é uma medição nova, com script próprio.

### 8.3 Antes × depois na validação

Validação com 13.490 medições nos dois rótulos. A persistência é "o futuro é igual ao agora". As árvores são as escolhidas
pelas regras do projeto (Tarefa 3 e Tarefa 4), treinadas só no treino.

| Modelo | F1 macro antes | F1 macro depois | Folhas antes → depois | Critério e profundidade/folha mínima, antes → depois |
|---|---|---|---|---|
| Persistência | 0,7221 | 0,6355 | — | — |
| Árvore da Tarefa 3 (oficial) | 0,7457 | 0,6863 | 16 → 29 | Gini 4/50 → Gini 5/50 |
| Ajustada sem peso | 0,7553 | 0,6820 | 4 → 29 | Gini 2/500 → Gini 5/50 |
| Ajustada com peso {OK 1; RISCO 2; FALHA 1,5} | 0,7600 | 0,6851 | 16 → 40 | Gini 4/100 → entropia 6/100 |

O F1 macro não se compara entre os dois rótulos. A persistência cai de 0,7221 para 0,6355 porque o alvo mudou, e não
porque o método piorou. Por isso, a comparação útil é o ganho sobre a persistência (8.4) e as taxas de acerto por
transição, abaixo.

| Modelo | Recall de FALHA, antes → depois | Recall de RISCO, antes → depois | Precisão de FALHA, antes → depois |
|---|---|---|---|
| Persistência | 0,809 → 0,498 | 0,488 → 0,512 | — |
| Árvore da Tarefa 3 | 0,779 → 0,478 | 0,490 → 0,477 | 0,846 → 0,737 |
| Ajustada sem peso | 0,722 → 0,480 | 0,601 → 0,454 | 0,948 → 0,743 |
| Ajustada com peso | 0,754 → 0,505 | 0,564 → 0,532 | 0,910 → 0,643 |

| Modelo | OK → FALHA: acerto antes → depois (medições) | Acerto quando o futuro muda, antes → depois | FALHA → OK: acerto antes → depois |
|---|---|---|---|
| Persistência | 0 % (491) → 0 % (201) | 0 % → 0 % | — |
| Árvore da Tarefa 3 | 1,8 % (9 de 491) → 18,4 % (37 de 201) | 23,4 % → 39,6 % | 16,4 % → 73,7 % |
| Ajustada sem peso | 0,2 % (1 de 491) → 18,4 % (37 de 201) | 35,9 % → 40,5 % | 66,8 % → 75,3 % |
| Ajustada com peso | 0,6 % (3 de 491) → 16,4 % (33 de 201) | 33,3 % → 36,1 % | 58,0 % → 44,8 % |

O que se lê nessas tabelas:

- A precisão de FALHA cai com o piso (0,910 para 0,643 na ajustada com peso). Na seção 7.2 a precisão subia, com o rótulo
  anterior. Com o rótulo novo, uma previsão de FALHA é menos confiável nesta validação. A validação tem 592 FALHAs no
  alvo, contra 3.736 antes, então as duas medidas não são diretamente comparáveis.
- O recall de FALHA da árvore oficial fica abaixo do da persistência (0,478 contra 0,498).
- O acerto em OK → FALHA sobe de 0,6 % (3 de 491) para 16,4 % (33 de 201) na ajustada com peso, e de 1,8 % para 18,4 %
  na oficial. São poucos casos, e o IC desse acerto não foi medido.
- Em FALHA → OK, a oficial acerta 73,7 % (antes, 16,4 %) e a ajustada com peso acerta 44,8 % (antes, 58,0 %). A oficial
  melhora nesse caso e a ajustada piora. É o que foi medido; a causa não foi investigada.

### 8.4 Ganho sobre a persistência, com IC 95 % por fluxo

**Método.** Bootstrap por fluxo: 2.000 reamostras (parâmetro do script), com semente 16. Cada reamostra sorteia os fluxos
com reposição, e cada medição pesa quantas vezes o fluxo dela caiu no sorteio. O F1 macro é recalculado com esses pesos,
e o IC 95 % é o intervalo entre os percentis 2,5 e 97,5. A validação e a dobra têm 79 fluxos cada. As comparações entre
antes e depois usam o mesmo sorteio e as mesmas medições, casadas pela chave `(fluxo_id, t)`.

**Dobra interna.** O treino é dividido em 60 % iniciais, por tempo, com folga de 3 medições por fluxo no corte (divisão do
P4). Em cada divisão, a árvore é escolhida dentro da própria divisão: a regra da Tarefa 3 para a oficial e a da Tarefa 4
(56 combinações) para as ajustadas. Por isso, o valor da oficial na dobra não é comparável ao da seção 3 (0,7246), que
usou Gini 4/50 fixo.

Validação (ganho = F1 da árvore − F1 da persistência):

| Árvore | Ganho antes [IC 95 %] | Ganho depois [IC 95 %] |
|---|---|---|
| Árvore da Tarefa 3 | +0,0236 [+0,0107; +0,0330] | +0,0508 [+0,0023; +0,0627] |
| Ajustada sem peso | +0,0332 [+0,0196; +0,0450] | +0,0464 [-0,0013; +0,0576] |
| Ajustada com peso | +0,0379 [+0,0255; +0,0480] | +0,0496 [+0,0246; +0,0598] |

Dobra interna:

| Árvore | Escolhida antes → depois | Ganho antes [IC 95 %] | Ganho depois [IC 95 %] |
|---|---|---|---|
| Persistência (F1) | — | 0,7145 | 0,6512 |
| Árvore da Tarefa 3 | Gini 3/500 (8 folhas) → Gini 5/50 (23) | +0,0202 [+0,0094; +0,0291] | +0,0316 [-0,0114; +0,0490] |
| Ajustada sem peso | entropia 5/100 (29) → entropia 2/200 (4) | +0,0347 [+0,0217; +0,0461] | +0,0309 [+0,0100; +0,0438] |
| Ajustada com peso | Gini 5/50 (30) → entropia 5/100 (21) | +0,0391 [+0,0276; +0,0499] | +0,0346 [+0,0080; +0,0476] |

Diferenças pareadas (mesmo sorteio; IC 95 % entre colchetes):

| Comparação | Validação | Dobra interna |
|---|---|---|
| Árvore da Tarefa 3: ganho depois − antes | +0,0272 [-0,0233; +0,0387] | +0,0114 [-0,0324; +0,0311] |
| Ajustada sem peso: ganho depois − antes | +0,0132 [-0,0365; +0,0286] | -0,0037 [-0,0257; +0,0106] |
| Ajustada com peso: ganho depois − antes | +0,0116 [-0,0142; +0,0238] | -0,0046 [-0,0327; +0,0091] |
| Ajustada com peso − Tarefa 3, antes | +0,0144 [+0,0068; +0,0218] | +0,0190 [+0,0080; +0,0300] |
| Ajustada com peso − Tarefa 3, depois | -0,0012 [-0,0084; +0,0241] | +0,0030 [-0,0073; +0,0249] |

O que se lê:

- Pontualmente, o ganho sobe: a oficial vai de +0,0236 para +0,0508, e a ajustada com peso, de +0,0379 para +0,0496.
- O IC da diferença depois − antes inclui zero nas três árvores, na validação e na dobra. **Não há prova de que o ganho
  sobre a persistência ficou maior com o piso.** O IC da oficial depois começa em +0,0023, e o da ajustada sem peso
  começa em -0,0013: nessas duas, o ganho não é claramente positivo a 95 %.
- Na dobra, o ganho da ajustada com peso cai de +0,0391 para +0,0346. A diferença não é significativa, mas vai no
  sentido contrário ao da validação.
- A vantagem da ajustada com peso sobre a oficial, que existia no rótulo anterior (+0,0144 na validação, IC de +0,0068 a
  +0,0218), some no rótulo novo (-0,0012, IC de -0,0084 a +0,0241). Com o rótulo novo, as duas são praticamente empatadas
  no F1 macro (0,6851 contra 0,6863).

### 8.5 Ressalvas medidas

1. **Ganho não comprovadamente maior.** Ver 8.4: nas três árvores, a diferença de ganho inclui zero.
2. **Recall de FALHA cai.** Oficial de 0,779 para 0,478; ajustada com peso de 0,754 para 0,505. A árvore deixa passar
   mais FALHAs do que antes, e a precisão também cai (8.3). O alvo tem menos FALHAs (592 na validação, contra 3.736), então
   as medidas são de outra população.
3. **Árvore maior.** A oficial vai de 16 para 29 folhas, a ajustada sem peso de 4 para 29, e a ajustada com peso de 16
   para 40. A profundidade máxima passa de 4 para 5 (oficial) e para 6 (ajustada com peso). A regra de escolha não foi
   trocada para segurar o tamanho (`SPEC-piso-regra3.md`, decisão 2), e o painel da página foi refeito para essas folhas
   (`SPEC-arvore-na-pagina.md`).
4. **F1 incomparável entre rótulos.** Ver 8.3: a persistência cai de 0,7221 para 0,6355 com o alvo novo.
5. **Ajustada com peso praticamente empatada com a oficial** no F1 macro: 0,6851 contra 0,6863, com diferença de -0,0012
   (IC de -0,0084 a +0,0241).
6. **Regiões (F1 macro na validação).** Na Europa, a oficial fica abaixo da persistência (0,432 contra 0,463); antes,
   ficava acima (0,748 contra 0,746). No Brasil, a oficial e a persistência empatam (0,536 contra 0,537); antes, a
   oficial ficava abaixo (0,479 contra 0,493). A ajustada com peso no Brasil tem 0,534.
7. **Persistência da dobra não confere com a seção 3.** A seção 3 diz 0,7141; a divisão do P4, usada aqui, dá 0,7145. A
   seção 3 foi feita com uma divisão de script anterior, que não ficou salva. As variantes testadas
   (`variantes_dobra_antes.py`, log ao lado) não reproduzem 0,7141: dividindo pelas linhas do treino inteiro, a
   persistência da dobra é 0,7134. A diferença de 0,0004 não muda nenhuma conclusão, mas é um conflito medido, e a seção
   3 não foi reescrita.
8. **O teto da seção 7.1 não foi medido de novo.** Os números 0,77 de F1, 13 % de acerto em OK → FALHA e 68 % de episódios
   de uma medição são do rótulo anterior. O boosting não foi refeito com o rótulo novo.

### 8.6 Peso de classe e decisões que ficam com o dono

- **Peso mantido** {OK 1; RISCO 2; FALHA 1,5}, por decisão do dono. A varredura de 32 combinações
  (`data/analise_piso_regra3/varredura_pesos.log`) não achou nenhuma com ganho acima de 0,005 de F1 macro nas duas
  medidas (validação e dobra). A melhor na validação (RISCO 2,5 / FALHA 2) ganha +0,0079 na validação e perde -0,0036
  na dobra (`varredura_pesos.csv`).
- **Piso mantido em 30.** A reversão é possível com `PISO_AUMENTO_FALHA_PCT = None`: com esse valor, o rótulo sai igual
  ao de antes (`conferir_rotulo_piso.py`).
- **Tamanho das árvores.** Se 40 folhas incomodar, apertar a regra de escolha é decisão à parte, a ser medida então
  (`SPEC-piso-regra3.md`, decisão 2).
- **Liberação da professora.** O registro dela no diário da Tarefa 4 (seção 4) é do dono; o agente não edita o diário.

### 8.7 Leitura

Com o piso, o alvo deixa de carregar as FALHAs de pico de milissegundos: FALHA cai de 23,8 % para 5,4 % das linhas do
modelo. A árvore com peso ainda ganha da persistência (IC de +0,0246 a +0,0598 na validação), mas essa diferença não ficou
comprovadamente maior que antes. A ajustada perde a vantagem sobre a oficial. A precisão e o recall de FALHA caem, e o
acerto em OK → FALHA continua baixo, em poucos casos. As medidas desta seção são da mesma validação que escolhe a árvore,
então servem para comparar os rótulos; o número honesto de cada árvore só sai no teste da Tarefa 5.
