// pulsos.js: o desenho de um pulso no <canvas> (SPEC-visualizacao.md, "Comportamento da página", item 2).
//
// Só DESENHA: recebe o contexto 2D (já escalado para o sistema do mapa), o pulso e a fração `p` de 0 a 1 do trajeto. Quem
// guarda a lista de pulsos vivos e decide quando soltá-los e encerrá-los é o mapa.js.

import { ehTimeout } from "./tempo.js";

// --- Constantes do pulso --------------------------------------------------------------------------------

// Duração do pulso NA TELA (segundos reais), proporcional ao RTT real da medição, com piso e teto para o pulso
// continuar visível (RTT de 10 ms duraria um piscar) e não ficar parado (RTT de vários segundos).
const SEGUNDOS_DE_TELA_POR_MS = 0.006; // 300 ms de RTT = 1,8 s na tela
const DURACAO_MINIMA_S = 0.6; // piso
const DURACAO_MAXIMA_S = 2.5; // teto

// Timeout não tem RTT: o pulso sai, para no meio do caminho e mostra um X antes de sumir.
const DURACAO_TIMEOUT_S = 2.0; // duração total na tela
const PONTO_DO_TIMEOUT = 0.5; // onde o pulso morre: fração do caminho (0 = sonda, 1 = destino)
const PARTE_VIAJANDO_TIMEOUT = 0.5; // fração da duração gasta indo até lá; o resto é o X parado

// Rastro atrás do pulso, como fração do caminho, e tamanhos de desenho (unidades do mapa).
const RASTRO = 0.14;
const RAIO_DO_PULSO = 5;
const LARGURA_DO_RASTRO = 3;
const LARGURA_DA_BASE_DO_RASTRO = 5.5; // base preta atrás da cor, para o rastro aparecer sobre qualquer fundo
const TAMANHO_DO_X = 7;

// Segurança de desempenho: se passarem de tantos pulsos ao mesmo tempo, os mais antigos somem primeiro.
// Pico de pulsos vivos medido no replay atual (mesma regra de duração de `duracaoNaTela`): 64 a 60x, 159 a 300x e 416 a
// 900x; a 1800x seriam ~799. A página só oferece 60x, 300x e 900x (`VELOCIDADES` em app.js), então o teto de 800 dá
// folga de quase 2x no pior caso. Se alguém oferecer uma velocidade maior (ou pulsos mais longos), meça de novo.
const MAXIMO_DE_PULSOS = 800;

// A rota do fluxo selecionado ganha uma faixa larga e translúcida (a linha cheia ou tracejada continua visível por baixo).
const LARGURA_DO_DESTAQUE = 11;
const OPACIDADE_DO_DESTAQUE = 0.55;

// --- Pulsos ---------------------------------------------------------------------------------------------

// Duração do pulso na tela (segundos reais): proporcional ao RTT, entre o piso e o teto.
function duracaoNaTela(medicao) {
  if (ehTimeout(medicao)) {
    return DURACAO_TIMEOUT_S;
  }
  const proporcional = medicao.rtt * SEGUNDOS_DE_TELA_POR_MS;
  return Math.min(DURACAO_MAXIMA_S, Math.max(DURACAO_MINIMA_S, proporcional));
}

// Desenha o rastro do trecho [u0, u1] da rota: segue os vértices da rota, então faz as mesmas curvas da linha desenhada.
// O traço sai duas vezes no mesmo caminho: base preta mais grossa e a cor da classe por cima (como o X do timeout).
function tracarRastro(ctx, rota, u0, u1, cor, tinta) {
  ctx.beginPath();
  rota.pontosEntre(u0, u1).forEach(([x, y], i) => {
    if (i === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.strokeStyle = tinta;
  ctx.lineWidth = LARGURA_DA_BASE_DO_RASTRO;
  ctx.stroke();
  ctx.strokeStyle = cor;
  ctx.lineWidth = LARGURA_DO_RASTRO;
  ctx.stroke();
}

// A "cabeça" do pulso: um losango da cor da classe, com borda preta.
function desenharCabeca(ctx, x, y, cor, tinta) {
  ctx.beginPath();
  ctx.moveTo(x, y - RAIO_DO_PULSO);
  ctx.lineTo(x + RAIO_DO_PULSO, y);
  ctx.lineTo(x, y + RAIO_DO_PULSO);
  ctx.lineTo(x - RAIO_DO_PULSO, y);
  ctx.closePath();
  ctx.fillStyle = cor;
  ctx.fill();
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = tinta;
  ctx.stroke();
}

// O X de timeout: um X preto grosso sobre uma base da cor da classe, no ponto onde o pulso morreu.
function desenharX(ctx, x, y, cor, tinta) {
  ctx.save(); // o `lineCap` abaixo vale só para o X; não vaza para os outros desenhos
  ctx.lineCap = "butt";
  for (const [largura, estilo] of [[7, cor], [3, tinta]]) {
    ctx.beginPath();
    ctx.moveTo(x - TAMANHO_DO_X, y - TAMANHO_DO_X);
    ctx.lineTo(x + TAMANHO_DO_X, y + TAMANHO_DO_X);
    ctx.moveTo(x + TAMANHO_DO_X, y - TAMANHO_DO_X);
    ctx.lineTo(x - TAMANHO_DO_X, y + TAMANHO_DO_X);
    ctx.lineWidth = largura;
    ctx.strokeStyle = estilo;
    ctx.stroke();
  }
  ctx.restore();
}

// Pulso normal: p de 0 a 1; a primeira metade vai da sonda ao destino, a segunda volta.
// Com `semRastro` (movimento reduzido) só a cabeça é desenhada.
function desenharPulsoNormal(ctx, pulso, p, tinta, semRastro) {
  const indo = p < 0.5;
  const u = indo ? 2 * p : 2 - 2 * p;
  // O rastro fica atrás da cabeça: do lado da sonda na ida, do lado do destino na volta.
  const rastro = indo ? [Math.max(0, u - RASTRO), u] : [u, Math.min(1, u + RASTRO)];
  if (!semRastro) {
    tracarRastro(ctx, pulso.rota, rastro[0], rastro[1], pulso.cor, tinta);
  }
  const [x, y] = pulso.rota.posicaoEm(u);
  desenharCabeca(ctx, x, y, pulso.cor, tinta);
}

// Pulso de timeout: vai até PONTO_DO_TIMEOUT, para e fica o X até acabar o tempo.
function desenharPulsoTimeout(ctx, pulso, p, tinta, semRastro) {
  if (p < PARTE_VIAJANDO_TIMEOUT) {
    const u = (p / PARTE_VIAJANDO_TIMEOUT) * PONTO_DO_TIMEOUT;
    if (!semRastro) {
      tracarRastro(ctx, pulso.rota, Math.max(0, u - RASTRO), u, pulso.cor, tinta);
    }
    const [x, y] = pulso.rota.posicaoEm(u);
    desenharCabeca(ctx, x, y, pulso.cor, tinta);
    return;
  }
  const [x, y] = pulso.rota.posicaoEm(PONTO_DO_TIMEOUT);
  desenharX(ctx, x, y, pulso.cor, tinta);
}

// A faixa translúcida sobre a rota do fluxo selecionado (segue os mesmos vértices da linha desenhada).
function desenharDestaqueDaRota(ctx, rota, cor) {
  ctx.save();
  ctx.globalAlpha = OPACIDADE_DO_DESTAQUE;
  ctx.strokeStyle = cor;
  ctx.lineWidth = LARGURA_DO_DESTAQUE;
  ctx.beginPath();
  rota.pontos.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
  ctx.stroke();
  ctx.restore();
}

export { MAXIMO_DE_PULSOS, desenharDestaqueDaRota, desenharPulsoNormal, desenharPulsoTimeout, duracaoNaTela };
