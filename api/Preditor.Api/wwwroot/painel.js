// painel.js: placar e feed das últimas previsões conferidas (SPEC-visualizacao.md, "Comportamento da página", item 6).
//
// Só escreve no DOM com textContent. As contas do placar vêm de placar.js (que só compara e soma campos do JSON); aqui se
// montam as linhas do feed uma vez e depois só se trocam os números.

import { NOME_DA_CLASSE, TEXTO_ACERTOU, TEXTO_ERROU, criarCelula, criarChip } from "./comum.js";
import { acertou, ultimasConferencias } from "./placar.js";

// Linhas do feed das últimas previsões conferidas (decisão visual: cabe no painel em 1280x720 junto com o resto).
const LINHAS_DO_FEED = 3;

// --- Placar e feed -------------------------------------------------------------------------------

// "82,9 %" (uma casa, vírgula); sem conferidas ainda, um traço. É só a razão entre dois contadores do placar.
function formatarPorcentagem(acertos, conferidas) {
  if (conferidas === 0) {
    return "--";
  }
  const pct = (100 * acertos) / conferidas;
  return `${pct.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

// Prepara as linhas do feed (vazias): hora, conexão, previsto, aconteceu e a marca de acerto ou erro. Cada linha é um
// botão: clicar (ou Enter / Espaço) abre o cartão do fluxo dela. `aoSelecionar(f, origem, porTeclado)` recebe o botão da
// linha (para devolver o foco a ele depois) e se o "clique" veio do teclado (`detail` 0).
function montarFeed(lista, aoSelecionar) {
  const linhas = [];
  for (let i = 0; i < LINHAS_DO_FEED; i += 1) {
    const item = document.createElement("li");
    const raiz = document.createElement("button");
    raiz.type = "button";
    raiz.className = "feed-linha feed-vazia";
    const linha = {
      raiz,
      f: null, // fluxo da conferência que a linha mostra agora
      fluxo: criarCelula("span", "", "feed-fluxo"),
      previsto: criarCelula("span", "", "feed-previsto"),
      real: criarCelula("span", "", "feed-real"),
      marca: criarCelula("span", "", "feed-marca"),
    };
    raiz.append(linha.fluxo, linha.previsto, linha.real, linha.marca);
    raiz.addEventListener("click", (evento) => linha.f !== null && aoSelecionar(linha.f, raiz, evento.detail === 0));
    item.append(raiz);
    lista.append(item);
    linhas.push(linha);
  }
  return linhas;
}

// Escreve uma conferência numa linha do feed: conexão, previsto -> aconteceu e ✓ / ✗ (com o texto
// ACERTOU / ERROU para leitor de tela e dica). Só textContent: nada do JSON vira HTML.
function escreverLinhaDoFeed(linha, medicao, rotulo) {
  const ok = acertou(medicao);
  linha.f = medicao.f;
  linha.raiz.classList.remove("feed-vazia");
  linha.raiz.classList.toggle("feed-erro", !ok);
  linha.raiz.setAttribute("aria-label", `Ver a conexão ${rotulo}: o sistema previu ${NOME_DA_CLASSE[medicao.previsto]}, aconteceu ${NOME_DA_CLASSE[medicao.futuro]}, ${ok ? TEXTO_ACERTOU : TEXTO_ERROU}`);
  linha.fluxo.textContent = rotulo;
  linha.fluxo.title = rotulo;
  linha.previsto.replaceChildren(criarChip(medicao.previsto));
  linha.real.replaceChildren(criarChip(medicao.futuro));
  linha.marca.textContent = ok ? "✓" : "✗";
  linha.marca.title = ok ? TEXTO_ACERTOU : TEXTO_ERROU;
}

// Quais conferências o feed mostra: as dos fluxos de regiões ligadas e, com "só erros", só as previsões erradas.
function aceitaNoFeed(estado) {
  return (medicao) => estado.visivel[medicao.f] && (!estado.soErros || !acertou(medicao));
}

function atualizarPlacar(estado, elementos, partes) {
  const { placar, medicoes, conferencias } = estado.tempo;
  const escrever = (campos, acertos) => {
    campos.acertos.textContent = acertos;
    campos.conferidas.textContent = placar.conferidas;
    campos.pct.textContent = formatarPorcentagem(acertos, placar.conferidas);
  };
  escrever(elementos.placar.arvore, placar.acertosArvore);
  escrever(elementos.placar.persistencia, placar.acertosPersistencia);

  const ultimas = ultimasConferencias(placar, medicoes, conferencias, LINHAS_DO_FEED, aceitaNoFeed(estado));
  partes.feed.forEach((linha, i) => {
    if (i < ultimas.length) {
      escreverLinhaDoFeed(linha, ultimas[i], estado.rotulos[ultimas[i].f]);
    } else {
      linha.f = null;
      linha.raiz.classList.add("feed-vazia");
    }
  });
}

// O painel só é reescrito quando o relógio alcança mais uma conferência, quando o placar é trocado (pulo no tempo) ou
// quando o filtro do feed muda: fora disso, não se gastam 60 quadros por segundo à toa.
function atualizarPlacarSeMudou(estado, elementos, partes) {
  const { placar } = estado.tempo;
  const { desenhado } = partes;
  if (desenhado.placar === placar && desenhado.proxima === placar.proxima && desenhado.filtro === estado.versaoDoFiltro) {
    return;
  }
  partes.desenhado = { placar, proxima: placar.proxima, filtro: estado.versaoDoFiltro };
  atualizarPlacar(estado, elementos, partes);
}

export { atualizarPlacarSeMudou, formatarPorcentagem, montarFeed };
