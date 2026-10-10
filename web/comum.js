// comum.js: pequenas funções de texto e de DOM usadas por mais de um arquivo da página (app.js e cartao.js).
//
// Nada aqui calcula métrica nem rótulo: só formata o que já vem no JSON e cria elementos (sempre com textContent, nunca
// innerHTML: o texto do JSON jamais é interpretado como HTML).
//
// Linguagem para quem não é da área: o JSON e o CSS continuam com os códigos do projeto (OK, RISCO, FALHA); só o que
// aparece na tela é traduzido, e a tradução mora aqui, em um lugar só.

const TEXTO_ACERTOU = "Acertou";
const TEXTO_ERROU = "Errou";

// Como cada classe aparece na tela. A cor e o texto andam juntos (nunca só cor). "Problema" não quer dizer "fora do ar":
// a classe FALHA inclui também a conexão que ficou muito mais lenta que o normal dela (RFC §8.4, linhas 1 a 3).
const NOME_DA_CLASSE = { OK: "Normal", RISCO: "Atenção", FALHA: "Problema" };
const SIGLA_DA_CLASSE = { OK: "N", RISCO: "A", FALHA: "P" }; // a letra do quadradinho de previsão no mapa

// Países do dataset por extenso (só para exibir; o JSON traz o código de duas letras).
const NOME_DO_PAIS = { BR: "Brasil", DE: "Alemanha", JP: "Japão", PT: "Portugal", SG: "Singapura", US: "Estados Unidos" };

function nomeDoPais(codigo) {
  return NOME_DO_PAIS[codigo] ?? codigo;
}

// A sonda (primeiro campo do `fluxo_id`) e a cidade do destino (último nó da rota, escrito como "Cidade (dst_addr)").
function detalhesDoFluxo(fluxo) {
  const ultimoTrecho = fluxo.trechos[fluxo.trechos.length - 1];
  return {
    sonda: fluxo.id.split("|")[0],
    cidade: ultimoTrecho.nos[ultimoTrecho.nos.length - 1].nome.split(" (")[0],
  };
}

// "Ponto 6349 → Frankfurt": o ponto de medição no Brasil (a sonda) e a cidade do destino.
function rotuloDoFluxo(fluxo) {
  const { sonda, cidade } = detalhesDoFluxo(fluxo);
  return `Ponto ${sonda} → ${cidade}`;
}

// "2026-09-23T20:09:58.000Z" vira a data (dia/mês/ano) e a hora separadas, sempre em UTC (a hora real da medição).
function formatarInstante(segundos) {
  const iso = new Date(segundos * 1000).toISOString();
  return { data: `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`, hora: iso.slice(11, 19) };
}

// Etiqueta de texto de uma classe, com a cor dela (as cores `chip-ok`, `chip-risco` e `chip-falha` vêm do CSS).
function criarChip(classe) {
  const chip = document.createElement("span");
  chip.className = `chip chip-${classe.toLowerCase()}`;
  chip.textContent = NOME_DA_CLASSE[classe];
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

export { NOME_DA_CLASSE, SIGLA_DA_CLASSE, TEXTO_ACERTOU, TEXTO_ERROU, criarCelula, criarChip, detalhesDoFluxo, formatarInstante, nomeDoPais, rotuloDoFluxo };
