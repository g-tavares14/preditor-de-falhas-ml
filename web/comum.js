// comum.js: pequenas funções de texto e de DOM usadas por mais de um arquivo da página (app.js e cartao.js).
//
// Nada aqui calcula métrica nem rótulo: só formata o que já vem no JSON e cria elementos (sempre com textContent, nunca
// innerHTML: o texto do JSON jamais é interpretado como HTML).

const TEXTO_ACERTOU = "ACERTOU";
const TEXTO_ERROU = "ERROU";

// A sonda (primeiro campo do `fluxo_id`) e a cidade do destino (último nó da rota, escrito como "Cidade (dst_addr)").
function detalhesDoFluxo(fluxo) {
  const ultimoTrecho = fluxo.trechos[fluxo.trechos.length - 1];
  return {
    sonda: fluxo.id.split("|")[0],
    cidade: ultimoTrecho.nos[ultimoTrecho.nos.length - 1].nome.split(" (")[0],
  };
}

// "6349 → DE Frankfurt": a sonda, o país e a cidade do destino.
function rotuloDoFluxo(fluxo) {
  const { sonda, cidade } = detalhesDoFluxo(fluxo);
  return `${sonda} → ${fluxo.pais} ${cidade}`;
}

// "2026-09-23T20:09:58.000Z" vira a data e a hora separadas, sempre em UTC (a hora real da medição).
function formatarInstante(segundos) {
  const iso = new Date(segundos * 1000).toISOString();
  return { data: iso.slice(0, 10), hora: iso.slice(11, 19) };
}

// Etiqueta de texto de uma classe, com a cor dela (as cores `chip-ok`, `chip-risco` e `chip-falha` vêm do CSS).
function criarChip(classe) {
  const chip = document.createElement("span");
  chip.className = `chip chip-${classe.toLowerCase()}`;
  chip.textContent = classe;
  return chip;
}

function criarCelula(tag, texto, classe) {
  const celula = document.createElement(tag);
  celula.textContent = texto;
  if (classe) {
    celula.className = classe;
  }
  return celula;
}

export { TEXTO_ACERTOU, TEXTO_ERROU, criarCelula, criarChip, detalhesDoFluxo, formatarInstante, rotuloDoFluxo };
