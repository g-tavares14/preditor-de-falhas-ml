# Contorno do mundo

`countries-110m.json`: pacote npm `world-atlas` 2.0.2 (licença ISC, `LICENSE-world-atlas.txt`; dados do Natural Earth, domínio público).
Origem: <https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json>.

SHA-256 (para conferir que ninguém o alterou): `2516c915867c7baf18ddec727aec46c315541a07cfb3d79a6559b05d5e94eee8`

D3 (`d3-geo`, `d3-selection`, `d3-shape`) e TopoJSON (`topojson-client`) já não ficam aqui: são dependências do npm (`web/package.json`),
empacotadas pelo Vite, sem CDN.
