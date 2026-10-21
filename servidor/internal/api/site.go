package api

import (
	"net/http"
	"os"
	"path"
	"strings"
)

// rotasDoApp são as telas do app React (react-router): o navegador pede /testar ou /historico direto (um link, F5), e quem entrega a tela é
// o mesmo index.html do mapa. Qualquer outro caminho que não seja um arquivo do site é 404 de verdade (e não uma página em branco).
var rotasDoApp = map[string]bool{"/": true, "/testar": true, "/historico": true}

// ehRotaDoApp diz se o caminho é uma tela do app. A barra no fim ("/testar/") conta igual.
func ehRotaDoApp(caminho string) bool {
	if caminho != "/" {
		caminho = strings.TrimSuffix(caminho, "/")
	}
	return rotasDoApp[caminho]
}

// politicaDeCache diz por quanto tempo o navegador e o CloudFront podem guardar cada arquivo do site.
//   - o index.html e o aovivo.json mudam sem mudar de nome: o navegador pergunta antes de reusar (o index.html é a única porta de
//     entrada para os arquivos novos; o aovivo.json é regravado a cada minuto).
//   - assets/ tem o hash do conteúdo no nome (o Vite o põe): se o arquivo muda, o nome muda. Um ano e imutável.
//   - mapa/ (o contorno do mundo) quase nunca muda: um dia.
//   - o resto (replay.json, ícone) só muda quando a imagem é refeita: cinco minutos.
//
// Com o hash no nome, publicar uma versão nova não exige mais invalidar o CloudFront: o index.html é revalidado e aponta para os
// arquivos novos. (Só o replay.json, que mantém o nome, espera os cinco minutos.)
func politicaDeCache(caminho string) string {
	switch {
	case caminho == "/dados/aovivo.json", ehRotaDoApp(caminho), caminho == "/index.html":
		return "no-cache"
	case strings.HasPrefix(caminho, "/assets/"):
		return "public, max-age=31536000, immutable"
	case strings.HasPrefix(caminho, "/mapa/"):
		return "public, max-age=86400"
	default:
		return "public, max-age=300"
	}
}

// cspDoApp é a política de segurança das telas do app: só recursos da própria origem (a página não usa internet) e nenhum <base> que
// redirecione os caminhos relativos (`default-src` não cobre `base-uri`). Vai por cabeçalho, e não por <meta>, porque o servidor de
// desenvolvimento do Vite injeta um script em linha que a política bloquearia.
const cspDoApp = "default-src 'self'; base-uri 'none'"

// site serve a pasta do site (o index.html do app, assets/, mapa/, dados/) na raiz. As telas do app (`/testar`, `/historico`) recebem o
// index.html; o resto é arquivo ou 404.
func site(pasta string) http.Handler {
	arquivos := http.FileServer(semListagem{http.Dir(pasta)})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		caminho := r.URL.Path
		if ehRotaDoApp(caminho) {
			w.Header().Set("Content-Security-Policy", cspDoApp)
			if caminho != "/" {
				// O FileServer entrega a pasta "/" como index.html; as outras telas do app usam o mesmo arquivo.
				r = r.Clone(r.Context())
				r.URL.Path = "/"
			}
		}
		arquivos.ServeHTTP(&escritorComCache{ResponseWriter: w, cache: politicaDeCache(caminho)}, r)
	})
}

// semListagem tira do `http.FileServer` o que o ASP.NET nunca fazia: listar o conteúdo de uma pasta sem index.html,
// e servir arquivo oculto (`.DS_Store`, `.env` esquecido na pasta).
type semListagem struct{ http.FileSystem }

func (s semListagem) Open(nome string) (http.File, error) {
	for _, parte := range strings.Split(path.Clean("/"+nome), "/") {
		if strings.HasPrefix(parte, ".") {
			return nil, os.ErrNotExist
		}
	}
	arquivo, err := s.FileSystem.Open(nome)
	if err != nil {
		return nil, err
	}
	if info, err := arquivo.Stat(); err == nil && info.IsDir() {
		indice, err := s.FileSystem.Open(path.Join(nome, "index.html"))
		if err != nil {
			arquivo.Close()
			return nil, os.ErrNotExist
		}
		indice.Close()
	}
	return arquivo, nil
}

// escritorComCache põe o Cache-Control só em resposta 200 ou 304. Em um 404 não pode: o CloudFront guardaria o "não existe" por cinco
// minutos, e a página recém-publicada continuaria "faltando" depois que o arquivo aparecesse.
type escritorComCache struct {
	http.ResponseWriter
	cache   string
	cabecas bool
}

func (e *escritorComCache) WriteHeader(status int) {
	if !e.cabecas {
		e.cabecas = true
		if status == http.StatusOK || status == http.StatusNotModified {
			e.Header().Set("Cache-Control", e.cache)
		}
	}
	e.ResponseWriter.WriteHeader(status)
}

func (e *escritorComCache) Write(dados []byte) (int, error) {
	if !e.cabecas {
		e.WriteHeader(http.StatusOK)
	}
	return e.ResponseWriter.Write(dados)
}

// Unwrap deixa o `http.ResponseController` (e o `ServeContent`) alcançar o escritor de verdade.
func (e *escritorComCache) Unwrap() http.ResponseWriter { return e.ResponseWriter }

// servirAoVivo entrega o aovivo.json que o serviço ao vivo (Python) regrava num volume, fora da pasta do site.
// Ele troca o arquivo inteiro de uma vez (grava um .tmp e renomeia), então abrir aqui nunca pega um JSON pela metade.
func servirAoVivo(arquivo string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		aberto, err := os.Open(arquivo)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		defer aberto.Close()
		info, err := aberto.Stat()
		if err != nil || info.IsDir() {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", politicaDeCache("/dados/aovivo.json"))
		http.ServeContent(w, r, "aovivo.json", info.ModTime(), aberto)
	}
}
