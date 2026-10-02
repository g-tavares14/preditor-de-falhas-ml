// desenho.js: o que fica no SVG (por baixo do canvas): mapa-base, trechos, cabos, nós, legenda e o cartão do trecho
// (SPEC-visualizacao.md, "Comportamento da página", item 1). Usa os globais `d3` e `topojson` (web/vendor/).
//
// Tudo aqui é desenhado uma vez só, no carregamento. Não calcula métrica nem rótulo de classe.

import { LARGURA, amostrarCaminho, cabeNoMapa, encostam, pontoNaFracao, textoDoCaminho } from "./rotas.js";

// --- Constantes dos nós e dos trechos ------------------------------------------------------------------

// Cada tipo de nó tem uma FORMA própria (distinguível sem cor) e uma área (em unidades do mapa ao quadrado).
// Formas do d3.symbol: quadrado = sonda (spec); círculo = destino (spec); cruz = ponto de troca (pop); triângulo =
// estação de aterragem do cabo.
const FORMAS_DOS_NOS = {
  sonda: { forma: d3.symbolSquare, area: 150 },
  pop: { forma: d3.symbolCross, area: 70 },
  aterragem: { forma: d3.symbolTriangle, area: 110 },
  destino: { forma: d3.symbolCircle, area: 190 },
};

// Onde fica o nome de cada cabo: frações do comprimento do trecho mais longo do cabo (0 = primeira estação, 1 = última),
// na ordem em que são tentadas. Vale a primeira em que o nome não encosta em outro rótulo nem sai do mapa; a ordem
// prefere o meio e se afasta dele (decisão visual; sem fonte externa).
const FRACOES_DO_ROTULO = [0.5, 0.4, 0.6, 0.3, 0.7, 0.8, 0.2];

const ROTULO_DO_TRECHO = { terrestre: "Trecho terrestre", submarino: "Cabo submarino" };

// O km de um cabo no cartão é o do cabo inteiro desenhado, não o de um fluxo; o texto diz isso.
const SUFIXO_DO_CABO = " (traçado completo)";

// Folga, em pixels, entre o ponteiro e o cartão do trecho.
const FOLGA_DO_CARTAO = 14;

// Desenha a moldura da esfera e os contornos dos países (TopoJSON convertido em GeoJSON) no SVG.
function desenharMapaBase(svg, topologia, projecao) {
  const caminho = d3.geoPath(projecao);
  const raiz = d3.select(svg);
  // O mapa-base é só pano de fundo: o leitor de tela o ignora (aria-hidden).
  raiz.append("path").attr("class", "mapa-esfera").attr("aria-hidden", "true").attr("d", caminho({ type: "Sphere" }));
  const paises = topojson.feature(topologia, topologia.objects.countries);
  raiz.append("path").attr("class", "mapa-paises").attr("aria-hidden", "true").attr("d", caminho(paises));
}

// O caminho de uma forma de nó (d3.symbol) centrado em (0, 0); o chamador o move com `transform`.
function caminhoDaForma(tipo) {
  const { forma, area } = FORMAS_DOS_NOS[tipo];
  return d3.symbol().type(forma).size(area)();
}

// --- Cartão com o detalhe do trecho ---------------------------------------------------------------------

function esconderDetalhe(cartao) {
  cartao.raiz.hidden = true;
}

// Mostra o cartão perto de (x, y), em pixels dentro da área do mapa, sem deixá-lo sair dela. Só `textContent`:
// o texto vem do JSON e nunca é interpretado como HTML.
function mostrarDetalhe(cartao, trecho, x, y) {
  cartao.tipo.textContent = ROTULO_DO_TRECHO[trecho.tipo];
  cartao.nome.textContent = trecho.nome;
  // Sem separador de milhar: "5.475" lido como decimal confunde. Sem km (trecho terrestre sobreposto), a linha some.
  cartao.km.hidden = trecho.kmDoCartao === null;
  cartao.km.textContent = trecho.kmDoCartao === null ? "" : `${Math.round(trecho.kmDoCartao)} km${trecho.tipo === "submarino" ? SUFIXO_DO_CABO : ""}`;
  cartao.raiz.hidden = false; // precisa estar visível para medir

  const area = cartao.raiz.parentElement;
  const maximoX = Math.max(0, area.clientWidth - cartao.raiz.offsetWidth);
  const maximoY = Math.max(0, area.clientHeight - cartao.raiz.offsetHeight);
  cartao.raiz.style.left = `${Math.min(Math.max(0, x + FOLGA_DO_CARTAO), maximoX)}px`;
  cartao.raiz.style.top = `${Math.min(Math.max(0, y + FOLGA_DO_CARTAO), maximoY)}px`;
}

// Liga o mouse (passar o ponteiro), o toque (encostar) e o teclado (foco) de um trecho ao cartão.
function ligarDetalhe(grupo, trecho, meio, cartao, recebeFoco) {
  const area = cartao.raiz.parentElement;

  function mostrarNoPonteiro(evento) {
    const caixa = area.getBoundingClientRect();
    mostrarDetalhe(cartao, trecho, evento.clientX - caixa.left, evento.clientY - caixa.top);
  }

  // Foco por teclado: o cartão aparece no meio do trecho (as coordenadas do mapa viram pixels pela escala da tela).
  // Clicar ou tocar também dá foco, mas aí o cartão já está no ponteiro e não deve pular para o meio do trecho:
  // `:focus-visible` só vale quando o foco veio do teclado.
  function mostrarNoMeio() {
    const escala = area.clientWidth / LARGURA;
    mostrarDetalhe(cartao, trecho, meio[0] * escala, meio[1] * escala);
  }

  grupo.on("pointerenter pointermove", mostrarNoPonteiro);
  // Num toque o ponteiro "sai" assim que o dedo levanta; então o cartão de toque fica até tocar em outro lugar.
  grupo.on("pointerleave", (evento) => {
    if (evento.pointerType !== "touch") {
      esconderDetalhe(cartao);
    }
  });
  // Só os cabos recebem foco. Não basta tirar o tabindex dos outros: no Chrome, um elemento SVG que tem ouvinte de "focus"
  // vira focável pelo Tab mesmo sem tabindex (os ~dezenas de trechos terrestres entrariam na ordem do Tab).
  if (recebeFoco) {
    grupo.on("focus", (evento) => evento.currentTarget.matches(":focus-visible") && mostrarNoMeio());
    grupo.on("blur", () => esconderDetalhe(cartao));
    // O cabo é um botão: Enter e Espaço (que o clique já faz com o ponteiro) mostram o cartão dele de novo, por exemplo
    // depois de o ponteiro passar por ele e esconder o cartão enquanto o foco continua aqui.
    grupo.on("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault(); // Espaço não rola a página, nem toca o replay (app.js)
        mostrarNoMeio();
      }
    });
  }
}

// --- Desenho dos trechos, cabos e nós no SVG -----------------------------------------------------------

// Cada trecho vira um grupo com duas linhas: a linha visível (cheia = terrestre, tracejada = submarino, pelo CSS) e
// uma linha larga e transparente por baixo, só para o mouse e o dedo acertarem a linha fina.
// Devolve, por trecho, a amostra do caminho (pontos e km acumulado), de onde saem o rótulo do cabo e o cartão do teclado,
// o grupo desenhado (que o filtro por região mostra ou esconde) e se ele recebe foco (os cabos submarinos).
function desenharTrechos(svg, trechos, projecao, cartao) {
  const raiz = d3.select(svg).append("g").attr("class", "trechos");
  return trechos.map((trecho) => {
    const amostra = amostrarCaminho(trecho.caminho, projecao);
    const caminho = textoDoCaminho(amostra.pontos);
    const meio = pontoNaFracao(amostra, 0.5);
    const grupo = raiz.append("g").attr("class", `trecho trecho-${trecho.tipo}`);
    grupo.append("path").attr("class", "trecho-linha").attr("d", caminho);
    grupo.append("path").attr("class", "trecho-alvo").attr("d", caminho);
    const focavel = trecho.tipo === "submarino";
    if (focavel) {
      // Só os cabos (poucos) recebem foco, e juntos são uma parada só do Tab (o foco.js move as setas entre eles); os
      // muitos trechos terrestres respondem ao mouse e ao toque. Um elemento focável precisa de papel interativo: `button`
      // (como os selos), e o nome dele é o do cabo; Enter e Espaço mostram o cartão do cabo (ver `ligarDetalhe`).
      grupo.attr("tabindex", 0).attr("role", "button").attr("aria-label", `Cabo ${trecho.nome}, ${Math.round(trecho.kmDoCartao)} km${SUFIXO_DO_CABO}`);
    } else {
      grupo.attr("aria-hidden", "true");
    }
    ligarDetalhe(grupo, trecho, meio, cartao, focavel);
    return { amostra, grupo, focavel };
  });
}

// Caixas (x, y, largura, altura, em unidades do mapa) para decidir se dois desenhos encostam (ver `encostam`, em rotas.js).
function caixaDoTexto(texto) {
  const caixa = texto.node().getBBox(); // o navegador mede o texto já desenhado
  return { x: caixa.x, y: caixa.y, largura: caixa.width, altura: caixa.height };
}

// A caixa de um nó: o quadrado que contém a forma (área = lado ao quadrado), com um pouco de folga para a borda.
function caixaDoNo(tipo, x, y) {
  const metade = Math.sqrt(FORMAS_DOS_NOS[tipo].area) / 2 + 2;
  return { x: x - metade, y: y - metade, largura: 2 * metade, altura: 2 * metade };
}

// O nome de cada cabo uma vez só, no trecho mais longo daquele cabo. A posição é achada por tentativa: para cada fração
// de FRACOES_DO_ROTULO, em ordem, mede-se o texto (getBBox) e vale a primeira que cabe no mapa e não encosta em nada de
// `ocupados` (nós e rótulos já colocados); cada nome colocado entra em `ocupados`. Se nenhuma serve, fica a primeira
// que cabe no mapa e o console avisa. Nada aqui depende de nomes de cabos ou de quantos eles são.
// Devolve cada nome com o índice do trecho em que foi posto: o nome some junto com esse trecho (filtro por região).
function desenharRotulosDosCabos(grupo, trechos, amostras, ocupados) {
  const colocados = [];
  const maisLongo = new Map(); // nome do cabo -> índice do trecho mais longo
  trechos.forEach((trecho, i) => {
    if (trecho.tipo === "submarino" && (!maisLongo.has(trecho.nome) || trecho.km > trechos[maisLongo.get(trecho.nome)].km)) {
      maisLongo.set(trecho.nome, i);
    }
  });
  for (const [nome, i] of maisLongo) {
    const texto = grupo.append("text").attr("class", "cabo-rotulo").attr("aria-hidden", "true").text(nome);
    const candidatos = FRACOES_DO_ROTULO.map((fracao) => {
      const [x, y] = pontoNaFracao(amostras[i], fracao);
      texto.attr("x", x).attr("y", y - 7);
      return { x, y: y - 7, caixa: caixaDoTexto(texto) };
    });
    const dentro = candidatos.filter((candidato) => cabeNoMapa(candidato.caixa));
    const livre = dentro.find((candidato) => !ocupados.some((outro) => encostam(candidato.caixa, outro)));
    const escolhido = livre ?? dentro[0] ?? candidatos[0];
    if (livre === undefined) {
      console.warn(`Rótulo do cabo ${nome}: nenhuma posição livre entre ${FRACOES_DO_ROTULO.length} tentativas; ficou sobreposto.`);
    }
    texto.attr("x", escolhido.x).attr("y", escolhido.y);
    ocupados.push(escolhido.caixa);
    colocados.push({ texto, indiceDoTrecho: i });
  }
  return colocados;
}

// Cada nó com a forma do seu tipo; o nome vira dica nativa (<title>) e o destino leva a cidade ao lado (à esquerda, se
// à direita não couber no mapa). Devolve as caixas ocupadas pelos nós e pelos nomes dos destinos, para os nomes dos
// cabos fugirem delas. Devolve também, por nó, os elementos desenhados (a forma e, no destino, o nome da cidade).
function desenharNos(svg, nos, projecao) {
  const raiz = d3.select(svg);
  const ocupados = [];
  const elementos = [];
  for (const no of nos) {
    const [x, y] = projecao(no.ponto);
    const marca = raiz.append("path").attr("class", `no no-${no.tipo}`).attr("aria-hidden", "true").attr("d", caminhoDaForma(no.tipo));
    marca.attr("transform", `translate(${x} ${y})`);
    marca.append("title").text(no.cidade === null ? no.nome : `Destino: ${no.cidade} (${no.pais})`);
    ocupados.push(caixaDoNo(no.tipo, x, y));
    elementos.push([marca]);
    if (no.cidade !== null) {
      const rotulo = raiz.append("text").attr("class", "marca-rotulo").attr("aria-hidden", "true").attr("x", x + 11).attr("y", y + 4).text(no.cidade);
      let caixa = caixaDoTexto(rotulo);
      if (caixa.x + caixa.largura > LARGURA) {
        rotulo.attr("x", x - 11).attr("text-anchor", "end");
        caixa = caixaDoTexto(rotulo);
      }
      ocupados.push(caixa);
      elementos[elementos.length - 1].push(rotulo);
    }
  }
  return { ocupados, elementos };
}

// Os ícones da legenda usam as mesmas formas do mapa: cada <svg data-forma="tipo"> da legenda recebe o seu.
function desenharIconesDaLegenda(raizDaLegenda) {
  for (const icone of raizDaLegenda.querySelectorAll("svg[data-forma]")) {
    const tipo = icone.dataset.forma;
    d3.select(icone).append("path").attr("class", `no no-${tipo}`).attr("d", caminhoDaForma(tipo)).attr("transform", "translate(12 12)");
  }
}

// --- Validação dos dados ---------------------------------------------------------------------------------

function exigir(condicao, mensagem) {
  if (!condicao) {
    throw new Error(`replay.json fora do formato: ${mensagem}`);
  }
}

function ehPonto(ponto) {
  return Array.isArray(ponto) && ponto.length === 2 && ponto.every(Number.isFinite);
}

// Confere o que o desenho assume dos fluxos: cada trecho tem tipo conhecido, caminho de ao menos 2 pontos e nós de
// tipo conhecido. Um dado fora disso lança um erro claro (a página o mostra) em vez de desenhar errado ou quebrar no meio.
function validarFluxos(fluxos) {
  exigir(Array.isArray(fluxos) && fluxos.length > 0, "a lista de fluxos está vazia");
  for (const fluxo of fluxos) {
    exigir(Array.isArray(fluxo.trechos) && fluxo.trechos.length > 0, `o fluxo ${fluxo.id} não tem trechos`);
    fluxo.trechos.forEach((trecho, i) => {
      const onde = `fluxo ${fluxo.id}, trecho ${i + 1}`;
      exigir(Object.hasOwn(ROTULO_DO_TRECHO, trecho.tipo), `${onde}: tipo de trecho desconhecido (${trecho.tipo})`);
      exigir(typeof trecho.nome === "string" && Number.isFinite(trecho.km), `${onde}: falta nome ou km`);
      exigir(Array.isArray(trecho.caminho) && trecho.caminho.length >= 2, `${onde}: o caminho tem menos de 2 pontos`);
      exigir(trecho.caminho.every(ehPonto), `${onde}: ponto do caminho inválido (esperado [longitude, latitude])`);
      exigir(Array.isArray(trecho.nos) && trecho.nos.length > 0, `${onde}: sem nós`);
      for (const no of trecho.nos) {
        exigir(Object.hasOwn(FORMAS_DOS_NOS, no.tipo), `${onde}: tipo de nó desconhecido (${no.tipo})`);
        exigir(typeof no.nome === "string" && ehPonto(no.ponto), `${onde}: nó sem nome ou sem ponto válido`);
      }
    });
  }
}

export {
  desenharIconesDaLegenda,
  desenharMapaBase,
  desenharNos,
  desenharRotulosDosCabos,
  desenharTrechos,
  esconderDetalhe,
  validarFluxos,
};
