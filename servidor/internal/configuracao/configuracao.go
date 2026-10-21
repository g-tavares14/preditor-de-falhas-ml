// Package configuracao lê as variáveis de ambiente do servidor. Os nomes com "__" são os mesmos que os arquivos do Compose já usavam
// quando a API era em C# (appsettings), para que o `docker-compose.prod.yml` da instância continue valendo.
package configuracao

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

type Configuracao struct {
	// Servidor__Endereco: onde escutar. No contêiner, ":8080".
	Endereco string
	// ServicoModelo__Url e ServicoModelo__TimeoutSegundos: o microserviço Python. A URL vem daqui, nunca do pedido.
	ModeloURL   string
	ModeloPrazo time.Duration
	// Limites__PedidosPorMinuto e Limites__CorpoMaximoBytes: o que protege a API pública (ela não tem login).
	PedidosPorMinuto int
	CorpoMaximoBytes int64
	// Banco__Arquivo: o arquivo SQLite. A pasta é criada se não existir.
	ArquivoBanco string
	// Web__Pasta: onde estão o index.html e os assets do site. Web__ArquivoAoVivo: o aovivo.json que o serviço ao vivo regrava
	// (fica num volume, fora da pasta do site; vazio = o arquivo, se existir, sai de dentro da pasta do site).
	PastaDoSite   string
	ArquivoAoVivo string
	// Web__OrigensConfiaveis: as origens (esquema + domínio, separadas por vírgula) de onde um navegador pode mandar POST para a API, além da
	// própria. Atrás do CloudFront o `Host` que chega aqui pode ser o da instância, e aí o `Origin` do navegador (o endereço público) não
	// bateria com ele: o POST da tela Testar levaria 403. Ex.: https://d3csgsins36z0x.cloudfront.net
	OrigensConfiaveis []string
}

// Padrao são os valores do desenvolvimento local: `go run ./cmd/preditor` de dentro de servidor/.
func Padrao() Configuracao {
	return Configuracao{
		Endereco:         ":5053",
		ModeloURL:        "http://127.0.0.1:8001",
		ModeloPrazo:      10 * time.Second, // a previsão leva milissegundos; mais que isso é serviço travado
		PedidosPorMinuto: 60,
		CorpoMaximoBytes: 16_384,
		ArquivoBanco:     "dados/preditor.db",
		PastaDoSite:      "../web/dist",
	}
}

// DoAmbiente parte do Padrao e troca o que estiver definido. Valor mal escrito é erro na partida, não um padrão silencioso.
func DoAmbiente(buscar func(string) (string, bool)) (Configuracao, error) {
	c := Padrao()

	texto := func(nome string, destino *string) {
		if v, ok := buscar(nome); ok && v != "" {
			*destino = v
		}
	}
	var erro error
	inteiro := func(nome string, destino *int64) {
		v, ok := buscar(nome)
		if !ok || v == "" {
			return
		}
		n, err := strconv.ParseInt(v, 10, 64)
		if err != nil || n < 1 {
			erro = fmt.Errorf("%s=%q: tem de ser um inteiro positivo", nome, v)
			return
		}
		*destino = n
	}

	texto("Servidor__Endereco", &c.Endereco)
	texto("ServicoModelo__Url", &c.ModeloURL)
	texto("Banco__Arquivo", &c.ArquivoBanco)
	texto("Web__Pasta", &c.PastaDoSite)
	texto("Web__ArquivoAoVivo", &c.ArquivoAoVivo)

	if v, ok := buscar("Web__OrigensConfiaveis"); ok && strings.TrimSpace(v) != "" {
		for _, origem := range strings.Split(v, ",") {
			origem = strings.TrimSpace(origem)
			if erro := validarOrigem(origem); erro != nil {
				return Configuracao{}, fmt.Errorf("Web__OrigensConfiaveis=%q: %w", origem, erro)
			}
			c.OrigensConfiaveis = append(c.OrigensConfiaveis, origem)
		}
	}

	segundos, pedidos, corpo := int64(c.ModeloPrazo/time.Second), int64(c.PedidosPorMinuto), c.CorpoMaximoBytes
	inteiro("ServicoModelo__TimeoutSegundos", &segundos)
	inteiro("Limites__PedidosPorMinuto", &pedidos)
	inteiro("Limites__CorpoMaximoBytes", &corpo)
	if erro != nil {
		return Configuracao{}, erro
	}
	c.ModeloPrazo, c.PedidosPorMinuto, c.CorpoMaximoBytes = time.Duration(segundos)*time.Second, int(pedidos), corpo
	return c, nil
}

// DoProcesso é DoAmbiente sobre as variáveis do processo.
func DoProcesso() (Configuracao, error) { return DoAmbiente(os.LookupEnv) }

// validarOrigem confere que é só `esquema://domínio[:porta]`, o formato que o `http.CrossOriginProtection` aceita.
func validarOrigem(origem string) error {
	u, err := url.Parse(origem)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" || u.Path != "" || u.RawQuery != "" || u.Fragment != "" || u.User != nil {
		return fmt.Errorf("tem de ser esquema://domínio[:porta], sem caminho (ex.: https://exemplo.cloudfront.net)")
	}
	return nil
}
