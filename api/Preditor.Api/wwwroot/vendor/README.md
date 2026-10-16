# Bibliotecas de terceiros (cópia local)

A página não usa internet em tempo de execução (decisão do dono, `SPEC-visualizacao.md`): estes três arquivos foram
baixados uma vez e ficam versionados. Para atualizar, baixe de novo a versão desejada, confira a licença e troque
a linha correspondente abaixo.

| Arquivo | Pacote npm | Versão | Licença | Origem do download |
|---|---|---|---|---|
| `d3.min.js` | `d3` | 7.9.0 | ISC (Mike Bostock) | https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js |
| `topojson-client.min.js` | `topojson-client` | 3.1.0 | ISC (Michael Bostock) | https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js |
| `countries-110m.json` | `world-atlas` | 2.0.2 | ISC (Michael Bostock); dados do Natural Earth, domínio público | https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json |

Textos das licenças (ISC exige manter o aviso de copyright e a permissão junto das cópias): `LICENSE-d3.txt`,
`LICENSE-topojson-client.txt` e `LICENSE-world-atlas.txt`, copiados do arquivo `LICENSE` de cada pacote no npm.
Observação: o `d3.min.js` é o pacote completo e embute, pelas dependências do d3 (`d3-delaunay`, `d3-array`), código do
`delaunator` (ISC, Mapbox), do `robust-predicates` (Unlicense, domínio público) e do `internmap` (ISC, Mike Bostock). Os
avisos deles não estão copiados aqui: ficam nos `LICENSE` desses pacotes no npm (a revisar se a página for publicada fora da turma).

O jsDelivr só serve o conteúdo publicado no npm; a versão e a licença de cada pacote foram conferidas no registro do
npm (`https://registry.npmjs.org/<pacote>/latest`) e no arquivo `LICENSE` de cada pacote.

SHA-256 dos arquivos baixados (para conferir que ninguém os alterou):

```
f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539  d3.min.js
25cd02ae486cc5063e0215a4e4cfb15de83700c87ac48bac4d57dc6aaf3ebb89  topojson-client.min.js
2516c915867c7baf18ddec727aec46c315541a07cfb3d79a6559b05d5e94eee8  countries-110m.json
```

Uso: `d3.min.js` e `topojson-client.min.js` criam os globais `d3` e `topojson`; `countries-110m.json` é o contorno
dos países em TopoJSON (resolução 1:110 milhões), lido com `fetch`.
