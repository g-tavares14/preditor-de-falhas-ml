// Comando preditor: o servidor público do projeto. Valida a medição, pergunta à Random Forest (microserviço Python), guarda a resposta
// no SQLite e serve o site. Configuração por variáveis de ambiente (ver internal/configuracao).
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"preditor/internal/api"
	"preditor/internal/banco"
	"preditor/internal/configuracao"
	"preditor/internal/modelo"
	"preditor/internal/previsao"
)

func main() {
	if err := executar(); err != nil {
		slog.Error("o servidor parou", "erro", err)
		os.Exit(1)
	}
}

func executar() error {
	cfg, err := configuracao.DoProcesso()
	if err != nil {
		return err
	}
	if _, err := os.Stat(filepath.Join(cfg.PastaDoSite, "index.html")); err != nil {
		// Não impede a partida (a API funciona sem o site), mas quem abrir a página vai ver 404: melhor avisar já.
		slog.Warn("a pasta do site não tem index.html", "Web__Pasta", cfg.PastaDoSite)
	}

	bd, err := banco.Abrir(cfg.ArquivoBanco)
	if err != nil {
		return err
	}
	defer bd.Fechar()

	cliente := modelo.NovoCliente(cfg.ModeloURL, cfg.ModeloPrazo)
	manipulador, err := api.Novo(api.Dependencias{
		Config:    cfg,
		Previsoes: &previsao.Servico{Modelo: cliente, Banco: bd},
		Banco:     bd,
		Modelo:    cliente,
	})
	if err != nil {
		return err
	}

	// Prazos de servidor público: sem eles, uma conexão que fica parada ocuparia o servidor para sempre.
	servidor := &http.Server{
		Addr:              cfg.Endereco,
		Handler:           manipulador,
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       2 * time.Minute,
		MaxHeaderBytes:    1 << 16,
	}

	// Ctrl+C e o `docker stop` (SIGTERM) terminam os pedidos em andamento antes de fechar.
	ctx, parar := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer parar()
	falha := make(chan error, 1)
	go func() {
		slog.Info("escutando", "endereco", cfg.Endereco, "modelo", cfg.ModeloURL, "site", cfg.PastaDoSite, "banco", cfg.ArquivoBanco)
		falha <- servidor.ListenAndServe()
	}()

	select {
	case err := <-falha:
		return err
	case <-ctx.Done():
	}
	slog.Info("encerrando")
	prazo, cancelar := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancelar()
	if err := servidor.Shutdown(prazo); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}
