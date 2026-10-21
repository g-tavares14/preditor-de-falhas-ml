package api

import (
	"embed"
	"io/fs"
	"net/http"
)

// O contrato escrito à mão e o Swagger UI (arquivos de terceiros em swagger/ui, sem CDN) vão dentro do binário.
//
//go:embed swagger/openapi.json
var contratoOpenAPI []byte

//go:embed swagger/ui
var arquivosDoSwagger embed.FS

// cspDoSwagger é mais frouxa que a do site só no estilo: o Swagger UI escreve `style` em linha. Script continua só da própria origem.
const cspDoSwagger = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'"

func contrato(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "public, max-age=300")
	w.Write(contratoOpenAPI)
}

// interfaceDoSwagger serve /swagger/ (a interface do Swagger UI).
func interfaceDoSwagger() http.Handler {
	ui, err := fs.Sub(arquivosDoSwagger, "swagger/ui")
	if err != nil {
		panic(err) // o caminho é constante e está embutido: se falhar, o binário está errado
	}
	arquivos := http.StripPrefix("/swagger/", http.FileServerFS(ui))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Security-Policy", cspDoSwagger)
		w.Header().Set("Cache-Control", "public, max-age=300")
		arquivos.ServeHTTP(w, r)
	})
}
