# Swagger UI (local, sem CDN)

Arquivos de terceiros copiados de `swagger-ui-dist@5.17.14` (npm), licença Apache-2.0 (`LICENSE`, `NOTICE`):

- `swagger-ui-bundle.js`
- `swagger-ui.css`

Origem: <https://www.npmjs.com/package/swagger-ui-dist/v/5.17.14>. Para atualizar: `npm pack swagger-ui-dist@<versão>` numa pasta vazia,
copiar só esses dois arquivos (e o `LICENSE`/`NOTICE`) e rodar `go test ./internal/api`. A página `index.html` e o `iniciar.js` daqui são nossos.
