// verificar-carga.js: rede de segurança do carregamento.
//
// Script CLÁSSICO (sem `type="module"`), de propósito: se o pacote principal falhar ao carregar (o navegador não mostra nada na
// página quando isso acontece), este arquivo, que não depende dele, continua rodando e avisa. O React troca o conteúdo de `#raiz`
// quando monta; se depois de ESPERA_MS o aviso "Carregando" ainda estiver lá, o app não subiu.

(function () {
  // O app carrega em ~1 s; 8 s dá folga a um computador lento sem deixar quem espera olhando um aviso vazio.
  var ESPERA_MS = 8000;
  var MENSAGEM = "A página não carregou por completo. Recarregue (F5).";

  setTimeout(function () {
    var aviso = document.getElementById("carregando");
    if (aviso !== null) {
      aviso.textContent = MENSAGEM;
    }
  }, ESPERA_MS);
})();
