// mapa.ts: monta o mapa (SVG + canvas) e devolve as operações que o motor do replay usa (SPEC-visualizacao.md).
//
// Este arquivo só ORQUESTRA; cada coisa fica no seu módulo:
//   rotas.ts    projeção e geometria das rotas (sem desenho)
//   desenho.ts  o que fica no SVG: mapa-base, trechos, cabos, nós, legenda e o cartão do trecho
//   pulsos.ts   o desenho de um pulso e do destaque da rota no canvas
//   selos.ts    o selo de previsão, o veredito e o alvo de clique e de teclado de cada fluxo
// Nada aqui calcula métrica nem rótulo: só desenha o que o replay já traz.
//
// O mapa é IMPERATIVO de propósito (SPEC-go-react.md): o laço de 60 quadros por segundo desenha no canvas e nunca passa pelo estado do
// React. O React só cria os elementos (`<svg>`, `<canvas>` e o cartão do trecho) e chama `criarMapa` quando eles existem.

import { select } from "d3-selection";
import type { Topology } from "topojson-specification";
import { ehTimeout } from "../logica/tempo";
import type { Classe, Cores, Fluxo, Medicao } from "../tipos";
import {
  apagarIconesDaLegenda,
  desenharIconesDaLegenda,
  desenharMapaBase,
  desenharNos,
  desenharRotulosDosCabos,
  desenharTrechos,
  esconderDetalhe,
  validarFluxos,
  type CartaoDoTrecho,
} from "./desenho";
import { criarGrupoDeFoco } from "./foco";
import { MAXIMO_DE_PULSOS, desenharDestaqueDaRota, desenharPulsoNormal, desenharPulsoTimeout, duracaoNaTela, type Pulso } from "./pulsos";
import { ALTURA, LARGURA, conferirCorte, criarProjecao, criarRotas, nosDistintos, trechosDistintos } from "./rotas";
import { atualizarNomeDoAlvo, criarSelos, desenharAlvosDosSelos, desenharAnelDeFoco, desenharSelo, duracaoDoVeredito, posicoesDosSelos } from "./selos";

export interface OpcoesDoMapa {
  svg: SVGSVGElement;
  canvas: HTMLCanvasElement;
  topologia: Topology;
  fluxos: Fluxo[];
  /** { OK, RISCO, FALHA, tinta, papel, acao } lidas das variáveis CSS (as cores continuam definidas só no CSS). */
  cores: Cores;
  /** Os elementos do cartão de detalhe do trecho (preenchido só com textContent). */
  cartao: CartaoDoTrecho;
  /** O elemento da legenda fixa, cujos <svg data-forma> recebem as formas dos nós. */
  raizDaLegenda: HTMLElement;
  /** O texto de cada fluxo ("Ponto 6349 → Frankfurt"), para o nome acessível do selo. */
  rotulos: string[];
  /**
   * Chamada quando alguém clica (ou aperta Enter ou Espaço) no selo do fluxo f; `origem` é o elemento do selo, para o app devolver o
   * foco a ele depois.
   */
  aoSelecionar: (f: number, origem: Element, porTeclado: boolean) => void;
  /** true para quem pede movimento reduzido (prefers-reduced-motion): o pulso é só a cabeça, sem o rastro. */
  semRastro?: boolean;
  /** A rotação da projeção ([longitude, latitude]); sem ela vale a do replay (rotas.ts). */
  rotacao?: [number, number];
}

export interface Mapa {
  /** Cria o pulso de uma medição; `agora` é o relógio da tela (segundos reais de animação). */
  soltarPulso(medicao: Medicao, agora: number): void;
  /**
   * A previsão de um fluxo foi conferida: o selo mostra ✓ ou ✗ por `duracao` segundos do relógio da animação (quem chama a calcula
   * com `duracaoDoVeredito`, que depende da velocidade).
   */
  marcarConferencia(f: number, acertou: boolean, agora: number, duracao: number): void;
  /** Quanto o veredito ✓ / ✗ dura no selo na velocidade dada (ver selos.ts); fica aqui para o motor não importar selos.ts. */
  duracaoDoVeredito: typeof duracaoDoVeredito;
  desenhar(agora: number): void;
  /**
   * Ao pular no tempo (ou reiniciar): apaga os pulsos em voo, sem soltar os das medições puladas, e põe em cada selo a última previsão
   * do fluxo até o novo instante. `ultimas[f]` é essa medição, ou null se o fluxo ainda não mediu.
   */
  restaurar(ultimas: (Medicao | null)[]): void;
  /** `lista[f]` = o fluxo f aparece? (rotas, pulsos e selos dos desligados somem). */
  definirVisiveis(lista: boolean[]): void;
  /** Destaca a rota do fluxo `f` (ou nenhuma, com null). */
  definirSelecionado(f: number | null): void;
  /** O elemento do selo do fluxo f (para devolver o foco a ele), ou null se a região dele está desligada. */
  alvoDoSelo(f: number): Element | null;
  /** Confere se alguma rota atravessa a borda da projeção (ver `conferirCorte`). */
  conferirCorte(): { rotas: number; pares: number; saltos: number };
  /** Desfaz tudo o que o mapa pôs no DOM (o React pode montar o mapa duas vezes em desenvolvimento). */
  destruir(): void;
}

export function criarMapa(opcoes: OpcoesDoMapa): Mapa {
  const { svg, canvas, topologia, fluxos, cores, cartao, raizDaLegenda, rotulos, aoSelecionar, semRastro = false, rotacao } = opcoes;
  validarFluxos(fluxos);
  svg.setAttribute("viewBox", `0 0 ${LARGURA} ${ALTURA}`);
  (canvas.parentElement as HTMLElement).style.aspectRatio = `${LARGURA} / ${ALTURA}`;

  const projecao = criarProjecao(rotacao);
  desenharMapaBase(svg, topologia, projecao);
  const rotas = criarRotas(fluxos, projecao);

  // Trechos (linhas), nomes dos cabos e nós: cada um desenhado uma vez só, mesmo que dezenas de fluxos o usem. O grupo dos nomes dos
  // cabos é criado antes dos nós (para ficar por baixo deles), mas só é preenchido depois, porque a posição de cada nome depende de
  // onde estão os nós e os nomes dos destinos.
  const trechos = trechosDistintos(fluxos);
  const desenhados = desenharTrechos(svg, trechos, projecao, cartao);
  const grupoDosNomes = select(svg).append("g").attr("class", "cabo-rotulos");
  const nos = nosDistintos(fluxos);
  const { ocupados, elementos: elementosDosNos } = desenharNos(svg, nos, projecao);
  const nomesDosCabos = desenharRotulosDosCabos(grupoDosNomes, trechos, desenhados.map((d) => d.amostra), ocupados);
  desenharIconesDaLegenda(raizDaLegenda);
  select(svg).on("pointerdown", (evento: PointerEvent) => {
    // Tocar fora de qualquer trecho fecha o cartão (o cartão de toque não some sozinho; ver `ligarDetalhe`).
    if (!(evento.target as Element).closest(".trecho")) {
      esconderDetalhe(cartao);
    }
  });

  // As grades de selos vão por último: fogem dos nós e dos nomes (de destinos e de cabos) já desenhados.
  const { posicoes: posicoesDosSelosNoMapa, ordem: ordemDosSelos } = posicoesDosSelos(fluxos, projecao, ocupados);
  let focado: number | null = null; // índice do fluxo cujo selo tem o foco do teclado (anel de foco), ou null
  const alvosDosSelos = desenharAlvosDosSelos(svg, posicoesDosSelosNoMapa, ordemDosSelos, rotulos, aoSelecionar, (f) => {
    focado = f;
    desenhar(ultimoInstante);
  });
  let selos = criarSelos(fluxos.length);
  const visivel = fluxos.map(() => true); // filtro por região: false = o fluxo não é desenhado
  let selecionado: number | null = null; // índice do fluxo selecionado (rota destacada), ou null

  // Ordem do Tab: o mapa tem DUAS paradas, uma para os cabos e outra para os selos; as setas andam dentro de cada grupo.
  const grupoDosCabos = criarGrupoDeFoco(desenhados.filter((d) => d.focavel).map((d) => d.grupo.node() as Element));
  const grupoDosSelos = criarGrupoDeFoco(ordemDosSelos.map((f) => alvosDosSelos[f].node() as Element));
  const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
  let pulsos: Pulso[] = [];
  let ultimoInstante = 0; // o último `agora` desenhado, para redesenhar quando o canvas é redimensionado
  let destruido = false;

  // Desenha todos os pulsos vivos no instante `agora` e descarta os que terminaram. Os de fluxos escondidos pelo filtro continuam
  // vivos (e atualizam o selo ao terminar), só não são desenhados: ao religar a região, o estado está certo.
  function desenhar(agora: number): void {
    if (destruido) {
      return;
    }
    ultimoInstante = agora;
    const k = canvas.width / LARGURA;
    ctx.setTransform(k, 0, 0, k, 0, 0);
    ctx.clearRect(0, 0, LARGURA, ALTURA);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    if (selecionado !== null && visivel[selecionado]) {
      desenharDestaqueDaRota(ctx, rotas[selecionado], cores.acao);
    }
    // Pulso que terminou = a medição voltou à sonda (ou o X do timeout sumiu): o selo do fluxo ganha a previsão dela.
    pulsos.filter((pulso) => (agora - pulso.nasceu) / pulso.duracao >= 1).forEach(encerrarPulso);
    pulsos = pulsos.filter((pulso) => (agora - pulso.nasceu) / pulso.duracao < 1);
    for (const pulso of pulsos) {
      if (!visivel[pulso.f]) {
        continue;
      }
      const p = Math.max(0, (agora - pulso.nasceu) / pulso.duracao);
      if (pulso.timeout) {
        desenharPulsoTimeout(ctx, pulso, p, cores.tinta, semRastro);
      } else {
        desenharPulsoNormal(ctx, pulso, p, cores.tinta, semRastro);
      }
    }
    // Os selos por cima dos pulsos: os de fluxos visíveis que já têm previsão.
    selos.forEach((selo, f) => {
      if (selo.previsto !== null && visivel[f]) {
        desenharSelo(ctx, selo, posicoesDosSelosNoMapa[f], agora, cores, f === selecionado);
      }
    });
    // O anel do foco do teclado por último, acima de tudo.
    if (focado !== null && visivel[focado]) {
      desenharAnelDeFoco(ctx, posicoesDosSelosNoMapa[focado], cores);
    }
  }

  // O selo guarda a previsão da medição mais recente do fluxo: um pulso lento (ou o do cap) que termina depois de um mais novo não a
  // sobrescreve.
  function encerrarPulso(pulso: Pulso): void {
    const selo = selos[pulso.f];
    if (pulso.t >= selo.t) {
      selo.previsto = pulso.previsto;
      selo.t = pulso.t;
      atualizarNomeDoAlvo(alvosDosSelos[pulso.f], rotulos[pulso.f], selo.previsto);
    }
  }

  // O canvas tem resolução própria (nítido em telas retina); o desenho continua em unidades do mapa. Mudar o tamanho limpa o canvas,
  // então os pulsos são redesenhados na hora, no mesmo instante, para não piscar um quadro em branco (com o replay pausado, ninguém
  // chamaria `desenhar` de novo).
  function ajustarCanvas(): void {
    const escala = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(canvas.clientWidth * escala));
    canvas.height = Math.max(1, Math.round(canvas.clientHeight * escala));
    desenhar(ultimoInstante);
  }
  const observador = new ResizeObserver(ajustarCanvas);
  observador.observe(canvas);
  ajustarCanvas();

  // Filtro por região: uma linha, um nó, um nome de cabo ou um selo só aparece se algum fluxo visível o usa.
  function aplicarVisibilidade(): void {
    const algumVisivel = (usuarios: Set<number>): boolean => [...usuarios].some((f) => visivel[f]);
    trechos.forEach((trecho, i) => desenhados[i].grupo.classed("oculto", !algumVisivel(trecho.usuarios)));
    nos.forEach((no, i) => elementosDosNos[i].forEach((elemento) => elemento.classed("oculto", !algumVisivel(no.usuarios))));
    for (const { texto, indiceDoTrecho } of nomesDosCabos) {
      texto.classed("oculto", !algumVisivel(trechos[indiceDoTrecho].usuarios));
    }
    alvosDosSelos.forEach((alvo, f) => alvo.classed("oculto", !visivel[f]));
    // Um cabo ou selo escondido não pode ser a parada do Tab: o grupo escolhe outro.
    grupoDosCabos.conferir();
    grupoDosSelos.conferir();
    desenhar(ultimoInstante); // com o replay pausado, ninguém mais redesenharia o canvas
  }

  return {
    soltarPulso(medicao, agora) {
      pulsos.push({
        f: medicao.f,
        t: medicao.t,
        previsto: medicao.previsto,
        rota: rotas[medicao.f],
        cor: cores[medicao.atual as Classe],
        nasceu: agora,
        duracao: duracaoNaTela(medicao),
        timeout: ehTimeout(medicao),
      });
      if (pulsos.length > MAXIMO_DE_PULSOS) {
        // Os pulsos cortados não somem sem deixar a previsão no selo.
        pulsos.slice(0, pulsos.length - MAXIMO_DE_PULSOS).forEach(encerrarPulso);
        pulsos = pulsos.slice(pulsos.length - MAXIMO_DE_PULSOS);
      }
    },

    marcarConferencia(f, acertou, agora, duracao) {
      selos[f].veredito = { acertou, ate: agora + duracao };
    },

    duracaoDoVeredito,

    desenhar,

    restaurar(ultimas) {
      pulsos = [];
      selos = ultimas.map((m) => (m === null ? criarSelos(1)[0] : { previsto: m.previsto, t: m.t, veredito: null }));
      selos.forEach((selo, f) => atualizarNomeDoAlvo(alvosDosSelos[f], rotulos[f], selo.previsto));
    },

    definirVisiveis(lista) {
      lista.forEach((valor, f) => (visivel[f] = valor));
      aplicarVisibilidade();
    },

    definirSelecionado(f) {
      selecionado = f;
      desenhar(ultimoInstante);
    },

    alvoDoSelo(f) {
      return visivel[f] ? alvosDosSelos[f].node() : null;
    },

    conferirCorte() {
      return conferirCorte(rotas);
    },

    destruir() {
      destruido = true;
      observador.disconnect();
      select(svg).on("pointerdown", null);
      svg.replaceChildren();
      apagarIconesDaLegenda(raizDaLegenda);
      esconderDetalhe(cartao);
      pulsos = [];
    },
  };
}
