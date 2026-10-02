// selos.js: o selo de previsão de cada fluxo, o veredito (acertou ou errou) e o alvo de clique e de teclado de cada um
// (SPEC-visualizacao.md, "Comportamento da página", itens 4 e 5).
//
// O selo é DESENHADO no <canvas> (`desenharSelo`); o alvo que recebe clique e foco é um <rect> do SVG por baixo do canvas
// (`desenharAlvosDosSelos`). A posição de cada selo vem de `posicoesDosSelos`.

import { cabeNoMapa, chaveDoPonto, destinoDoFluxo, encostam } from "./rotas.js";

// --- Constantes do selo de previsão ---------------------------------------------------------------------

// Cada fluxo tem um selo: um quadradinho com a letra da classe que a árvore PREVÊ (O, R ou F) para 12 min depois da
// última medição que já voltou à sonda. Os selos de um mesmo destino ficam juntos numa grade ao lado do nó de destino
// (são 79 fluxos para 7 destinos: um selo por fluxo, solto no mapa, viraria poluição). O selo é estado, não evento:
// fica até a próxima previsão do mesmo fluxo. Tamanhos em unidades do mapa (decisão visual; sem fonte externa).
const CELULA_DO_SELO = 11;
const FOLGA_DO_SELO = 2;
const COLUNAS_DA_GRADE = 5;
const DISTANCIA_DO_NO = 12; // entre o centro do nó de destino e a grade (maior que a metade do nó, para não encostar)
const FONTE_DO_SELO = "bold 9px ui-monospace, Menlo, Consolas, monospace";

// Ao conferir, o selo mostra o veredito (✓ ou ✗, desenhado em traço) em vez da letra da previsão, por um tempo curto, em
// segundos reais de animação. Ele é renovado a cada conferência do fluxo; se durasse mais que o intervalo entre duas
// conferências do mesmo fluxo, o selo ficaria sempre em ✓ / ✗ e a letra da previsão sumiria (medido: 0,3 s fixos deixavam o
// selo 97 % do tempo em veredito a 900x). Por isso o veredito dura, no máximo, esta fração desse intervalo e nunca mais
// que o teto abaixo. Os fluxos são medidos quase juntos, então as conferências chegam em rajadas, e com 0,4 a captura de
// um quadro logo depois da rajada mostrava ✓/✗ na maioria dos selos (medido a 900x: maioria em ✓/✗ em 21 % dos quadros).
// 0,25 deixa a letra à vista em ~3/4 do tempo e o veredito ainda dura alguns quadros (decisão visual da V7b).
const FRACAO_DO_INTERVALO_EM_VEREDITO = 0.25;
const DURACAO_MAXIMA_DO_VEREDITO_S = 0.3; // teto, para a 60x o veredito não ficar longo à toa

// Cada selo tem um alvo de clique e de foco (um <rect> do SVG, por baixo do canvas) um pouco maior que ele: o anel de
// foco por teclado fica ao redor do selo, fora da área que o canvas cobre. Selecionar um fluxo põe um anel no selo.
const FOLGA_DO_ALVO_DO_SELO = 3;
const FOLGA_DO_ANEL_DO_SELO = 2.5;
// O anel de foco do teclado é maior e mais grosso que o de "selecionado", com uma moldura clara por baixo.
const FOLGA_DO_ANEL_DE_FOCO = 4.5;
const LARGURA_DO_ANEL_DE_FOCO = 3;
const LARGURA_DA_MOLDURA_DO_FOCO = 6.5;

// --- Selos de previsão e conferência ---------------------------------------------------------------------

// Quanto tempo o veredito fica no selo, em segundos reais. `intervaloDaSimulacaoS` é o intervalo típico entre duas medições
// do mesmo fluxo, em segundos DA SIMULAÇÃO (vem dos dados; null se não há como medir): na velocidade `velocidade` (x), ele
// vira `intervalo / velocidade` segundos reais entre duas conferências do fluxo.
function duracaoDoVeredito(velocidade, intervaloDaSimulacaoS) {
  if (intervaloDaSimulacaoS === null) {
    return DURACAO_MAXIMA_DO_VEREDITO_S;
  }
  return Math.min(DURACAO_MAXIMA_DO_VEREDITO_S, (FRACAO_DO_INTERVALO_EM_VEREDITO * intervaloDaSimulacaoS) / velocidade);
}

// Posição (canto superior esquerdo) de cada selo, na grade do destino do fluxo. Fluxos com o mesmo destino (mesmo ponto
// do último nó) dividem a grade, na ordem de `fluxos`. Cada grade tenta quatro cantos do nó, nesta ordem (direita e
// abaixo, esquerda e abaixo, direita e acima, esquerda e acima), e fica no primeiro que cabe no mapa e não encosta em
// nada de `ocupados` (nós, nomes de destinos e de cabos) nem nas grades já colocadas. Se nenhum serve, o primeiro que cabe.
// Devolve `posicoes` (por fluxo) e `ordem`: os índices dos fluxos na ordem em que as grades são lidas (destino por destino,
// cada grade da esquerda para a direita e de cima para baixo), que é a ordem das setas do teclado.
function posicoesDosSelos(fluxos, projecao, ocupados) {
  const porDestino = new Map();
  fluxos.forEach((fluxo, indice) => {
    const chave = chaveDoPonto(destinoDoFluxo(fluxo));
    porDestino.set(chave, [...(porDestino.get(chave) ?? []), indice]);
  });

  const passo = CELULA_DO_SELO + FOLGA_DO_SELO;
  const posicoes = new Array(fluxos.length);
  const ordem = [];
  const colocadas = [];
  for (const indices of porDestino.values()) {
    const [x, y] = projecao(destinoDoFluxo(fluxos[indices[0]]));
    const colunas = Math.min(COLUNAS_DA_GRADE, indices.length);
    const largura = colunas * passo - FOLGA_DO_SELO;
    const altura = Math.ceil(indices.length / COLUNAS_DA_GRADE) * passo - FOLGA_DO_SELO;
    const direita = x + DISTANCIA_DO_NO;
    const esquerda = x - DISTANCIA_DO_NO - largura;
    const abaixo = y + DISTANCIA_DO_NO;
    const acima = y - DISTANCIA_DO_NO - altura;
    const candidatos = [[direita, abaixo], [esquerda, abaixo], [direita, acima], [esquerda, acima]].map(([cx, cy]) => ({
      x: cx,
      y: cy,
      caixa: { x: cx, y: cy, largura, altura },
    }));
    const dentro = candidatos.filter((candidato) => cabeNoMapa(candidato.caixa));
    const livre = dentro.find((c) => ![...ocupados, ...colocadas].some((outro) => encostam(c.caixa, outro)));
    const escolhido = livre ?? dentro[0] ?? candidatos[0];
    if (livre === undefined) {
      console.warn(`Selos do destino em (${x.toFixed(0)}, ${y.toFixed(0)}): nenhum canto livre; ficaram sobrepostos.`);
    }
    colocadas.push(escolhido.caixa);
    ordem.push(...indices);
    indices.forEach((indice, k) => {
      posicoes[indice] = [escolhido.x + (k % COLUNAS_DA_GRADE) * passo, escolhido.y + Math.floor(k / COLUNAS_DA_GRADE) * passo];
    });
  }
  return { posicoes, ordem };
}


// Um selo por fluxo: o que a árvore previu (null até a primeira medição voltar), de qual medição (`t`) e o veredito
// em andamento (null, ou { acertou, ate } com `ate` no relógio da animação).
function criarSelos(quantidade) {
  return Array.from({ length: quantidade }, () => ({ previsto: null, t: -Infinity, veredito: null }));
}

// O ✓ e o ✗ em traço preto grosso, centrados em (x, y): distinguíveis pela forma, sem depender de cor.
function desenharVeredito(ctx, x, y, acertou, tinta) {
  const meio = CELULA_DO_SELO / 2 - 2.5;
  ctx.beginPath();
  if (acertou) {
    ctx.moveTo(x - meio, y);
    ctx.lineTo(x - meio / 3, y + meio * 0.8);
    ctx.lineTo(x + meio, y - meio * 0.8);
  } else {
    ctx.moveTo(x - meio, y - meio);
    ctx.lineTo(x + meio, y + meio);
    ctx.moveTo(x + meio, y - meio);
    ctx.lineTo(x - meio, y + meio);
  }
  ctx.lineWidth = 2.2;
  ctx.strokeStyle = tinta;
  ctx.stroke();
}

// Desenha o selo de um fluxo: quadrado da cor da classe prevista com a letra dela; durante o veredito, fundo branco com
// ✓ (acertou) ou ✗ (errou) no lugar da letra. O selo do fluxo selecionado leva um anel preto ao redor.
function desenharSelo(ctx, selo, [x, y], agora, cores, destacado) {
  if (destacado) {
    ctx.lineWidth = 3;
    ctx.strokeStyle = cores.tinta;
    const folga = FOLGA_DO_ANEL_DO_SELO;
    ctx.strokeRect(x - folga, y - folga, CELULA_DO_SELO + 2 * folga, CELULA_DO_SELO + 2 * folga);
  }
  const veredito = selo.veredito !== null && agora < selo.veredito.ate ? selo.veredito : null;
  ctx.fillStyle = veredito === null ? cores[selo.previsto] : cores.papel;
  ctx.fillRect(x, y, CELULA_DO_SELO, CELULA_DO_SELO);
  ctx.lineWidth = veredito === null ? 1.5 : 2.5;
  ctx.strokeStyle = cores.tinta;
  ctx.strokeRect(x, y, CELULA_DO_SELO, CELULA_DO_SELO);
  const meio = [x + CELULA_DO_SELO / 2, y + CELULA_DO_SELO / 2];
  if (veredito !== null) {
    desenharVeredito(ctx, meio[0], meio[1], veredito.acertou, cores.tinta);
    return;
  }
  ctx.fillStyle = cores.tinta;
  ctx.font = FONTE_DO_SELO;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(selo.previsto[0], meio[0], meio[1] + 0.5);
}

// O anel do selo que tem o foco do TECLADO, desenhado por cima de todos os selos (um selo vizinho não o cobre): um traço
// preto grosso sobre uma moldura clara, para aparecer sobre o mapa, as linhas e os outros selos. É mais forte que o anel de
// "selecionado" (`desenharSelo`), para os dois se distinguirem quando coincidem.
function desenharAnelDeFoco(ctx, [x, y], cores) {
  const folga = FOLGA_DO_ANEL_DE_FOCO;
  for (const [largura, cor] of [[LARGURA_DA_MOLDURA_DO_FOCO, cores.papel], [LARGURA_DO_ANEL_DE_FOCO, cores.tinta]]) {
    ctx.lineWidth = largura;
    ctx.strokeStyle = cor;
    ctx.strokeRect(x - folga, y - folga, CELULA_DO_SELO + 2 * folga, CELULA_DO_SELO + 2 * folga);
  }
}

// O nome do alvo (para o leitor de tela e a dica do mouse): o fluxo e, quando já existe, a previsão atual do selo.
function nomeDoAlvo(rotulo, previsto) {
  return previsto === null ? `Ver o fluxo ${rotulo}` : `Ver o fluxo ${rotulo}. Previsão da árvore: ${previsto}`;
}

// Os alvos de clique e de foco dos selos: um <rect> transparente do SVG sobre cada selo (o canvas fica por cima, com
// `pointer-events: none`, então o clique chega aqui). Enter e Espaço fazem o mesmo que o clique. Os <rect> entram no DOM na
// `ordem` das grades (a das setas e a da leitura); a lista devolvida é por fluxo.
//   aoSelecionar(f, origem, porTeclado): clique ou Enter / Espaço; `origem` é o <rect> (para devolver o foco a ele depois) e
//     `porTeclado` diz se veio de Enter ou Espaço.
//   aoFocar(f): o foco do teclado chegou ao selo do fluxo f (null quando ele sai): o mapa desenha o anel de foco.
function desenharAlvosDosSelos(svg, posicoes, ordem, rotulos, aoSelecionar, aoFocar) {
  const raiz = d3.select(svg).append("g").attr("class", "selos-alvo").attr("role", "group").attr("aria-label", "Selos de previsão, um por fluxo");
  const alvos = new Array(posicoes.length);
  for (const f of ordem) {
    const [x, y] = posicoes[f];
    const lado = CELULA_DO_SELO + 2 * FOLGA_DO_ALVO_DO_SELO;
    const alvo = raiz
      .append("rect")
      .attr("class", "selo-alvo")
      .attr("x", x - FOLGA_DO_ALVO_DO_SELO)
      .attr("y", y - FOLGA_DO_ALVO_DO_SELO)
      .attr("width", lado)
      .attr("height", lado)
      .attr("tabindex", 0) // o foco.js deixa só um dos selos na ordem do Tab
      .attr("role", "button")
      .attr("aria-label", nomeDoAlvo(rotulos[f], null));
    alvo.append("title").text(nomeDoAlvo(rotulos[f], null));
    alvo.on("click", (evento) => aoSelecionar(f, evento.currentTarget, evento.detail === 0));
    alvo.on("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault(); // Espaço não rola a página
        aoSelecionar(f, evento.currentTarget, true);
      }
    });
    // O anel só aparece para quem navega pelo teclado: no clique, o fluxo selecionado já ganha o seu anel.
    alvo.on("focus", (evento) => evento.currentTarget.matches(":focus-visible") && aoFocar(f));
    alvo.on("blur", () => aoFocar(null));
    alvos[f] = alvo;
  }
  return alvos;
}

// Atualiza o nome do alvo do fluxo f quando a previsão do selo muda.
function atualizarNomeDoAlvo(alvo, rotulo, previsto) {
  const nome = nomeDoAlvo(rotulo, previsto);
  if (alvo.attr("aria-label") !== nome) {
    alvo.attr("aria-label", nome).select("title").text(nome);
  }
}

export { atualizarNomeDoAlvo, criarSelos, desenharAlvosDosSelos, desenharAnelDeFoco, desenharSelo, duracaoDoVeredito, posicoesDosSelos };
