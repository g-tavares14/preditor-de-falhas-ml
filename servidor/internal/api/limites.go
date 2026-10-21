package api

import (
	"fmt"
	"net"
	"net/http"
	"strconv"
	"sync"
	"time"
)

// limitador deixa `max` pedidos por `janela` para cada chave (o endereço de quem pede). É uma janela fixa: a contagem de cada endereço
// começa no primeiro pedido dele e zera `janela` depois, como o limitador do ASP.NET que a API em C# usava.
type limitador struct {
	max    int
	janela time.Duration
	agora  func() time.Time

	mu        sync.Mutex
	contagens map[string]*contagem
	limpezaEm time.Time
}

type contagem struct {
	pedidos int
	expira  time.Time
}

func novoLimitador(max int, janela time.Duration, agora func() time.Time) *limitador {
	return &limitador{max: max, janela: janela, agora: agora, contagens: map[string]*contagem{}}
}

// permitir conta um pedido da chave. Se passou do limite, devolve false e quanto falta para a janela dela zerar.
func (l *limitador) permitir(chave string) (bool, time.Duration) {
	l.mu.Lock()
	defer l.mu.Unlock()
	agora := l.agora()

	// Sem esta varredura o mapa só cresceria: cada endereço novo ficaria lá para sempre. Uma vez por janela basta.
	if agora.After(l.limpezaEm) {
		for k, c := range l.contagens {
			if !agora.Before(c.expira) {
				delete(l.contagens, k)
			}
		}
		l.limpezaEm = agora.Add(l.janela)
	}

	c := l.contagens[chave]
	if c == nil || !agora.Before(c.expira) {
		c = &contagem{expira: agora.Add(l.janela)}
		l.contagens[chave] = c
	}
	if c.pedidos >= l.max {
		return false, c.expira.Sub(agora)
	}
	c.pedidos++
	return true, 0
}

// limitarPedidos devolve 429 quando um endereço passa do limite. A chave é o endereço da conexão (RemoteAddr).
func limitarPedidos(l *limitador, proximo http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		chave, _, err := net.SplitHostPort(r.RemoteAddr)
		if err != nil {
			chave = r.RemoteAddr
		}
		if ok, espera := l.permitir(chave); !ok {
			w.Header().Set("Retry-After", strconv.Itoa(int(espera.Seconds())+1))
			escreverProblema(w, problema{Title: "Pedidos demais. Tente de novo em instantes.", Status: http.StatusTooManyRequests})
			return
		}
		proximo.ServeHTTP(w, r)
	})
}

// limitarCorpo recusa corpo grande demais com 413. Recusa pelo `Content-Length` antes de ler qualquer byte; e, para o corpo que chega
// em pedaços (sem tamanho declarado), `MaxBytesReader` corta a leitura no limite (o handler converte o erro em 413).
func limitarCorpo(max int64, proximo http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.ContentLength > max {
			escreverProblema(w, problema{Title: "O corpo passa de " + strconv.FormatInt(max, 10) + " bytes.", Status: http.StatusRequestEntityTooLarge})
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, max)
		proximo.ServeHTTP(w, r)
	})
}

// recuperar transforma um pânico dentro de um handler em um 500 genérico, em vez de derrubar a conexão sem explicação.
func recuperar(proximo http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if erro := recover(); erro != nil && erro != http.ErrAbortHandler {
				falha(w, r, panicErro{erro})
			}
		}()
		proximo.ServeHTTP(w, r)
	})
}

type panicErro struct{ valor any }

func (p panicErro) Error() string { return fmt.Sprint("pânico: ", p.valor) }
