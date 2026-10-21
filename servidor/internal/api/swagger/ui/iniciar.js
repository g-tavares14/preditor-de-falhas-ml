// Liga o Swagger UI ao contrato escrito à mão (/api/openapi.json). Arquivo à parte, e não um <script> dentro do HTML, porque a CSP
// desta página não permite script inline.
window.ui = SwaggerUIBundle({
  url: "/api/openapi.json",
  dom_id: "#swagger-ui",
  deepLinking: true,
  tryItOutEnabled: false,
});
