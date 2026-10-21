package configuracao

import (
	"reflect"
	"testing"
	"time"
)

func ambiente(valores map[string]string) func(string) (string, bool) {
	return func(nome string) (string, bool) { v, ok := valores[nome]; return v, ok }
}

func TestDoAmbiente_semNadaUsaOPadrao(t *testing.T) {
	c, err := DoAmbiente(ambiente(nil))
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(c, Padrao()) {
		t.Errorf("sem variáveis devia ser o padrão: %+v", c)
	}
}

func TestDoAmbiente_trocaSoOQueFoiDefinido(t *testing.T) {
	c, err := DoAmbiente(ambiente(map[string]string{
		"ServicoModelo__Url":             "http://modelo:8001",
		"ServicoModelo__TimeoutSegundos": "3",
		"Web__ArquivoAoVivo":             "/vivo/aovivo.json",
		"Limites__PedidosPorMinuto":      "5",
		"Servidor__Endereco":             ":8080",
	}))
	if err != nil {
		t.Fatal(err)
	}
	if c.ModeloURL != "http://modelo:8001" || c.ModeloPrazo != 3*time.Second || c.ArquivoAoVivo != "/vivo/aovivo.json" ||
		c.PedidosPorMinuto != 5 || c.Endereco != ":8080" {
		t.Errorf("valores não aplicados: %+v", c)
	}
	if c.CorpoMaximoBytes != Padrao().CorpoMaximoBytes {
		t.Errorf("o que não foi definido fica no padrão: %d", c.CorpoMaximoBytes)
	}
}

func TestDoAmbiente_numeroMalEscritoEErroNaPartida(t *testing.T) {
	for _, valor := range []string{"abc", "0", "-5", "1.5"} {
		if _, err := DoAmbiente(ambiente(map[string]string{"Limites__PedidosPorMinuto": valor})); err == nil {
			t.Errorf("%q devia ser recusado", valor)
		}
	}
}

func TestDoAmbiente_origensConfiaveis(t *testing.T) {
	c, err := DoAmbiente(ambiente(map[string]string{"Web__OrigensConfiaveis": " https://d3csgsins36z0x.cloudfront.net , http://localhost:5173 "}))
	if err != nil {
		t.Fatal(err)
	}
	if len(c.OrigensConfiaveis) != 2 || c.OrigensConfiaveis[0] != "https://d3csgsins36z0x.cloudfront.net" || c.OrigensConfiaveis[1] != "http://localhost:5173" {
		t.Errorf("origens: %q", c.OrigensConfiaveis)
	}
	if semNada, _ := DoAmbiente(ambiente(nil)); len(semNada.OrigensConfiaveis) != 0 {
		t.Errorf("por padrão não há origem declarada: %q", semNada.OrigensConfiaveis)
	}
}

func TestDoAmbiente_origemMalEscritaEErroNaPartida(t *testing.T) {
	for _, origem := range []string{"cloudfront.net", "https://exemplo.net/caminho", "ftp://exemplo.net", "https://", "https://exemplo.net?x=1"} {
		if _, err := DoAmbiente(ambiente(map[string]string{"Web__OrigensConfiaveis": origem})); err == nil {
			t.Errorf("%q devia ser recusada", origem)
		}
	}
}
