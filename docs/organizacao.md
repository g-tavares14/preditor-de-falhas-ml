# Organização

Ler quando a tarefa **adiciona** entidade, use case, port, adapter, Protocol ou
pasta. Não copiar isto para o `AGENTS.md`.

## Onde cada coisa cai

| Mudança | Camada |
| --- | --- |
| Fórmula, invariante, valor (X, rótulo, predição) | `domain/` |
| “Fazer X com Y e Z” (coletar, rotular, treinar, gravar) | `application/` + port |
| HTTP, arquivo, S3, CLI, lib de ML, dataset PingER | `adapters/` |
| Use case sem I/O | `tests/` + fake em `tests/fakes.py` |
| Contrato HTTP/arquivo | `tests/` do adapter |

Pasta nova só com ≥2 módulos que mudam pelo mesmo motivo.

## Tipos (nessa ordem)

1. Função — operação dados → dados ou dados → efeito.
2. `dataclass` — dado + invariante simples.
3. Classe — estado compartilhado entre operações (sessão HTTP, lock).
4. Protocol — produção + fake de teste (ou segunda implementação real).

## Ports já existentes

- `MeasurementGateway`: `AtlasGateway` + `FakeGateway`.
- `DatasetStore`: `FileDataset` + `MemoryDataset`.

Port novo (ex.: `LabelPolicy`, `ObjectStore`, `PingerSource`): declarar em
`application/ports.py`, implementar no adapter, fake no teste do use case.
Não injetar `AtlasGateway`/`boto3`/`sklearn` no application.

## SOLID com parada

- **S:** uma razão de mudança por módulo. Não um arquivo por função.
- **O:** novo módulo quando `if`/`match` de tipo se repetir.
- **L:** ignore se não houver herança.
- **I:** sem protocolo de um implementador.
- **D:** o use case recebe o port. Sem container.

## Recusar

- Protocol com uma implementação
- Pasta com um arquivo
- Camada que só chama a de baixo
- Factory / Strategy / Singleton / Repository / Event / Plugin sem o problema de hoje
- Config genérica antes do segundo chamador
- DI container
- `services/` ou `infrastructure/` paralelos às três camadas

## Declaração no incremento que mexe em estrutura

- Pastas criadas e por quê.
- Tipos novos; se houve classe, o motivo.
- Port: produção + fake (ou segunda implementação).
- Gates do `AGENTS.md` e o resultado.
- Fluxo: entrada → regra → saída ou erro.
