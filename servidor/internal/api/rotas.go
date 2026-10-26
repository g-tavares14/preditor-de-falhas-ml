package api

import (
	"fmt"
	"net/http"
	"time"

	"preditor/internal/banco"
	"preditor/internal/configuracao"
	"preditor/internal/modelo"
	"preditor/internal/previsao"
)

// Dependencias é tudo o que o servidor HTTP precisa, já montado por quem o cria (`main` ou o teste).
type Dependencias struct {
	Config    configuracao.Configuracao
	Previsoes *previsao.Servico
	Banco     *banco.Banco
	Modelo    *modelo.Cliente
	// Agora existe para o teste fixar o relógio do limitador; nil = time.Now.
	Agora func() time.Time
}

// rotasDaAPI são os padrões de rota de /api/*, na mesma forma que o openapi.json descreve (o teste confere as duas listas).
func rotasDaAPI(h *manipuladores) map[string]http.HandlerFunc {
	return map[string]http.HandlerFunc{
		"POST /api/previsoes":   h.criar,
		"GET /api/previsoes":    h.listar,
		"GET /api/modelo":       h.ficha,
		"GET /api/saude":        h.saude,
		"GET /api/openapi.json": contrato, // o contrato descreve as rotas acima; ele mesmo fica de fora do openapi.json
	}
}

// Novo monta todas as rotas. Ordem de fora para dentro: recuperar de pânico, cabeçalhos, proteção contra POST de outra origem e, só
// para /api/*, o limite de pedidos por endereço e o de tamanho do corpo. O site estático e o /swagger/ ficam de fora do limite.
func Novo(d Dependencias) (http.Handler, error) {
	agora := d.Agora
	if agora == nil {
		agora = time.Now
	}
	h := &manipuladores{previsoes: d.Previsoes, banco: d.Banco, modelo: d.Modelo}

	api := http.NewServeMux()
	for padrao, manipulador := range rotasDaAPI(h) {
		api.HandleFunc(padrao, manipulador)
	}

	raiz := http.NewServeMux()
	raiz.Handle("/api/", limitarPedidos(novoLimitador(d.Config.PedidosPorMinuto, time.Minute, agora), limitarCorpo(d.Config.CorpoMaximoBytes, api)))
	raiz.Handle("GET /swagger/", interfaceDoSwagger()) // o próprio ServeMux redireciona /swagger para /swagger/
	// O aovivo.json do serviço ao vivo mora num volume; sem `Web__ArquivoAoVivo`, o arquivo (se existir) sai da pasta do site, como no
	// desenvolvimento local.
	if d.Config.ArquivoAoVivo != "" {
		raiz.HandleFunc("GET /dados/aovivo.json", servirAoVivo(d.Config.ArquivoAoVivo))
	}
	raiz.Handle("/", site(d.Config.PastaDoSite))

	// A API não tem cookie nem login, então não há sessão a sequestrar; mesmo assim, um navegador que mande POST vindo de outro site
	// (Origin ou Sec-Fetch-Site de fora) é recusado com 403. Curl e outros programas, que não mandam esses cabeçalhos, passam. A origem pública
	// (o CloudFront) entra em `Web__OrigensConfiaveis`: ver `configuracao.Configuracao`.
	protecao := http.NewCrossOriginProtection()
	// Sem isto o 403 sairia em texto puro; assim ele tem o mesmo formato de todo erro da API (e a tela Testar mostra o `title`).
	protecao.SetDenyHandler(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		escreverProblema(w, problema{Title: "Pedido de outro site recusado.", Status: http.StatusForbidden})
	}))
	for _, origem := range d.Config.OrigensConfiaveis {
		if err := protecao.AddTrustedOrigin(origem); err != nil {
			return nil, fmt.Errorf("origem confiável %q: %w", origem, err)
		}
	}
	return recuperar(cabecalhosGerais(protecao.Handler(raiz))), nil
}

func cabecalhosGerais(proximo http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		proximo.ServeHTTP(w, r)
	})
}
