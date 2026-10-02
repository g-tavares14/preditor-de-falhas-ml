// verificar-carga.js: rede de segurança do carregamento (SPEC-visualizacao.md).
//
// Script CLÁSSICO (sem `type="module"`), de propósito: se algum módulo de app.js falhar ao carregar (o navegador não
// mostra nada na página quando isso acontece), este arquivo, que não depende de nenhum módulo, continua rodando e avisa.
// Depois de ESPERA_MS, se o botão Tocar ainda estiver desabilitado e nenhum erro estiver visível, a página não carregou por
// completo: escreve o aviso no lugar do "Carregando o replay...".

(function () {
  // O replay local carrega em ~1 s; 8 s dá folga a um computador lento sem deixar quem espera olhando um aviso vazio.
  var ESPERA_MS = 8000;
  var MENSAGEM = "A página não carregou por completo. Recarregue (F5). Use `uv run python -m preditor servir`.";

  setTimeout(function () {
    var botao = document.getElementById("botao-tocar");
    var erro = document.getElementById("erro");
    var status = document.getElementById("status");
    if (botao === null || erro === null || !botao.disabled || !erro.hidden) {
      return; // carregou (botão habilitado) ou já há um erro à vista
    }
    if (status !== null) {
      status.hidden = true;
    }
    erro.textContent = MENSAGEM;
    erro.hidden = false;
  }, ESPERA_MS);
})();
