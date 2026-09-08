# Preditor de falhas ML

Integração Python com o RIPE Atlas para a equipe coletar medições de rede.
O fluxo consulta créditos, cria um ping pontual para **8.8.8.8** e busca seus
resultados pelo ID. O destino e a família IPv4 são fixos neste incremento.

Os resultados brutos ficam em memória. O armazenamento no Amazon S3 será um
incremento posterior, separado do acesso ao Atlas.

## Ambiente

Requer Python 3.12 ou superior e uv. Na raiz do repositório:

```bash
uv sync
```

`requests` é a única dependência direta de execução adicionada neste incremento:
ela faz as chamadas HTTP e mantém a sessão autenticada compartilhada. Ruff e
pytest são dependências de desenvolvimento.

## Usar a classe

O ponto de entrada é `from preditor_de_falhas_ml import AtlasClient`. Defina
`RIPE_ATLAS_API_KEY` no ambiente do seu processo com uma chave que tenha permissões
de **leitura de créditos** e **criação de medições**. A classe recebe a chave no
construtor; não carrega arquivos `.env` nem lê variáveis de ambiente por conta própria.

A chave fornecida tem prioridade sobre credenciais de `.netrc`. As configurações de
proxy e certificados do ambiente continuam sendo respeitadas.

Abra o interpretador do projeto:

```bash
uv run python
```

Se a chave estiver em um arquivo `.env` na raiz, o próprio uv pode carregá-lo
para o processo, sem dependência adicional:

```bash
uv run --env-file .env python
```

Consulte o saldo e crie uma medição pontual:

```python
import os

from preditor_de_falhas_ml import AtlasClient

with AtlasClient(os.environ["RIPE_ATLAS_API_KEY"]) as atlas:
    print("Créditos:", atlas.get_credits())
    measurement_id = atlas.create_sample(country_code="BR")
    print("ID da medição:", measurement_id)
```

O sample mede **8.8.8.8 por IPv4**, uma única vez, usando por padrão uma probe do
país informado e três pacotes. A criação consome créditos e devolve o ID antes de
os resultados estarem disponíveis. O Atlas seleciona as probes conforme sua
disponibilidade e as quotas da conta. O destino não é configurável neste incremento.
**8.8.8.8 é uma constante de produto**; mudar ou tornar configurável esse alvo
exige outro incremento.

Depois, na mesma sessão Python, consulte pelo ID já retornado:

```python
with AtlasClient(os.environ["RIPE_ATLAS_API_KEY"]) as atlas:
    results = atlas.get_results(measurement_id)
    print(results)
```

Uma lista vazia significa que ainda não há resultados disponíveis. Uma lista com
resultados também pode estar incompleta enquanto as probes executam a medição.
Para atualizar os resultados, repita apenas `get_results()` com o mesmo ID.
Em outra sessão Python, use o ID que foi exibido ao criar a medição.

| Operação                                                     | Entrada e retorno                                                                                                                   |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `AtlasClient(api_key, timeout=30.0)`                         | Chave explícita e timeout positivo em segundos, aplicado à conexão e à leitura HTTP.                                                |
| `get_credits()`                                              | Retorna o saldo inteiro de `current_balance`, incluindo zero.                                                                       |
| `create_sample(country_code="BR", probe_count=1, packets=3)` | País com duas letras, quantidade positiva de probes e entre 1 e 16 pacotes; retorna o ID inteiro. Todos os parâmetros são nomeados. |
| `get_results(measurement_id)`                                | ID inteiro positivo; retorna uma lista de dicionários com os resultados brutos.                                                     |
| `close()`                                                    | Fecha a sessão. O bloco `with` faz isso automaticamente, inclusive em caso de erro.                                                 |

O país é normalizado para maiúsculas; a API verifica se o código existe. Entradas
inválidas e respostas incompatíveis geram `ValueError`. Falhas HTTP geram
`requests.HTTPError`, com a resposta disponível em `.response`. Exceções levantadas
pelo envio HTTP são relançadas sem substituir o objeto, preservando subtipo,
mensagem, causa, traceback e atributos da biblioteca. Uma nota (`add_note`) acrescenta
a operação e uma orientação. O cliente não registra a chave nem copia o corpo da
resposta para suas mensagens ou notas.

Não há repetição automática nem acompanhamento em segundo plano. Se a criação
falhar por timeout ou conexão, confira suas medições na conta do Atlas antes de
reenviar: a requisição pode ter sido aceita e consumido créditos.

## Estrutura deste incremento

- `src/preditor_de_falhas_ml/`: pacote de produção, com a exportação pública em
  `__init__.py` e as operações HTTP em `atlas.py`.
- `tests/`: dois módulos verificam o contrato HTTP e a validação de entradas.
- `AtlasClient`: a classe se justifica pela sessão HTTP e autenticação
  compartilhadas entre operações. Não há outros tipos próprios, hierarquias,
  Protocol/ABC ou camadas intermediárias.

Fluxo: a equipe fornece a chave e seleciona o país e a quantidade de probes;
as entradas são validadas antes do HTTP, o Atlas cria o ping pontual para 8.8.8.8
e devolve seu ID; outra chamada busca os resultados brutos disponíveis ou informa
uma falha específica. Não há transformação dos resultados nesta etapa.

## Validação

Comandos executados neste incremento:

```bash
uv sync
uv run ruff format .
uv run ruff check .
uv run pytest
```

Resultado: sincronização concluída, formatter sem novas alterações, lint aprovado
e 77 testes passando. Os testes substituem o envio HTTP e verificam as requisições
preparadas pelo `requests`, incluindo autenticação, destino fixo, payload, erros,
resultados vazios e preservação dos campos brutos. Os casos de `.netrc` verificam a
prioridade da chave e a preservação dos proxies e certificados do ambiente.
Não exigem chave real nem consomem créditos. Os exemplos acima também foram
executados com HTTP simulado.
Em 07/09/2026, a consulta autenticada de créditos foi validada na API real usando
a chave do `.env`, sem exibi-la. A criação e a consulta de resultados continuam
validadas por testes com HTTP simulado; nenhuma medição real foi criada.

## Evolução prevista: Amazon S3

O próximo incremento de armazenamento poderá receber os resultados retornados por
`get_results()` e gravá-los no S3. A coleta continuará independente da gravação.
Os campos originais, inclusive ID da medição, probe, destino, timestamp e respostas
dos pacotes quando presentes, são preservados para permitir reprocessamento.

Bucket, formato persistido, organização dos objetos, credenciais AWS e dependências
serão definidos nessa etapa. Este incremento não cria integração S3, arquivos de
dados, CLI, medições recorrentes, cálculo de métricas ou treinamento ML.

## Referências

- [Autenticação com chave de API](https://atlas.ripe.net/docs/apis/rest-api-manual/authentication/api-keys/)
- [Consulta de créditos](https://atlas.ripe.net/docs/apis/rest-api-reference/credits/credits_retrieve)
- [Criação de medições](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/)
- [Seleção de probes](https://atlas.ripe.net/docs/apis/rest-api-manual/measurements/creating-measurements/probe-selection/)
- [Resultados de medições](https://atlas.ripe.net/docs/apis/rest-api-reference/measurements/measurements_results)
