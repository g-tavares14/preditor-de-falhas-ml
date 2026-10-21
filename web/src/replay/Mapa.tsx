// Mapa.tsx: o cartão do mapa: o filtro de regiões, o mapa (SVG com o mapa-base e as rotas, canvas com os pulsos e os selos) e a legenda.
//
// O mapa é IMPERATIVO (mapa/mapa.ts): o React só cria os elementos e, depois que eles existem, chama `criarMapa`. Os elementos que o
// mapa escreve por dentro (o <svg>, o <canvas>, o cartão do trecho, os ícones da legenda) ficam em componentes `memo` SEM props: o React
// nunca os reconcilia de novo, então nunca desfaz o que o D3 desenhou.

import { memo, useEffect, useRef, type Ref } from "react";
import type { Topology } from "topojson-specification";
import { criarMapa } from "../mapa/mapa";
import { ROTACAO_AO_VIVO } from "../mapa/rotas";
import type { Cores } from "../tipos";
import type { Motor } from "./motor";

/** As cores das classes vivem só no CSS (variáveis `--ok`, `--risco`, `--falha`, `--tinta`...); o canvas as lê daqui. */
function lerCoresDoCss(): Cores {
  const estilo = getComputedStyle(document.documentElement);
  const cor = (nome: string): string => estilo.getPropertyValue(nome).trim();
  return { OK: cor("--ok"), RISCO: cor("--risco"), FALHA: cor("--falha"), tinta: cor("--tinta"), papel: cor("--papel"), acao: cor("--acao") };
}

/** Os elementos que o mapa escreve por dentro, entregues por referência (o React não os reconcilia mais depois do primeiro desenho). */
interface RefsDoMapa {
  svg: Ref<SVGSVGElement>;
  canvas: Ref<HTMLCanvasElement>;
  detalhe: Ref<HTMLDivElement>;
  tipo: Ref<HTMLSpanElement>;
  nome: Ref<HTMLSpanElement>;
  km: Ref<HTMLSpanElement>;
}

const AreaDoMapa = memo(function AreaDoMapa({ refs }: { refs: RefsDoMapa }) {
  return (
    <div className="mapa" id="mapa">
      <svg id="mapa-svg" ref={refs.svg} role="group" aria-label="Mapa-múndi em traço, com as rotas, os cabos submarinos e os quadradinhos de previsão"></svg>
      <canvas id="mapa-canvas" ref={refs.canvas} aria-hidden="true"></canvas>
      {/* Cartão do trecho sob o mouse, o toque ou o foco: o mapa só escreve nele com textContent. É só visual: o leitor de tela já
          recebe o nome do cabo pelo próprio elemento focado. */}
      <div className="detalhe-trecho" id="detalhe-trecho" ref={refs.detalhe} aria-hidden="true" hidden>
        <span className="detalhe-tipo" ref={refs.tipo}></span>
        <span className="detalhe-nome" ref={refs.nome}></span>
        <span className="detalhe-km numero" ref={refs.km}></span>
      </div>
    </div>
  );
});

interface PropsDoMapa {
  motor: Motor;
  topologia: Topology;
  legenda: React.RefObject<HTMLElement | null>;
  /** Clique (ou Enter / Espaço) num selo do mapa. */
  aoSelecionar: (f: number, origem: Element, porTeclado: boolean) => void;
  aoErrar: (mensagem: string) => void;
  aoAlertar: (mensagem: string) => void;
}

/**
 * Cria o mapa depois que os elementos existem, liga-o ao motor e inicia o laço de animação; ao sair, desfaz tudo. Em desenvolvimento o
 * React 19 monta, desmonta e monta de novo (StrictMode): por isso o `destruir()` e o motor que reata o mapa novo ao estado atual.
 */
export function Mapa({ motor, topologia, legenda, aoSelecionar, aoErrar, aoAlertar }: PropsDoMapa) {
  const svg = useRef<SVGSVGElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const detalhe = useRef<HTMLDivElement>(null);
  const tipo = useRef<HTMLSpanElement>(null);
  const nome = useRef<HTMLSpanElement>(null);
  const km = useRef<HTMLSpanElement>(null);
  // O mapa chama o que estiver aqui no momento do clique: assim trocar o `aoSelecionar` não refaz o mapa.
  const selecionar = useRef(aoSelecionar);
  selecionar.current = aoSelecionar;
  // Estável entre renderizações (os refs são objetos fixos): `AreaDoMapa` nunca recebe props novas.
  const refs = useRef<RefsDoMapa>({ svg, canvas, detalhe, tipo, nome, km }).current;

  useEffect(() => {
    const elementos = { svg: svg.current, canvas: canvas.current, raiz: detalhe.current, tipo: tipo.current, nome: nome.current, km: km.current, legenda: legenda.current };
    if (!elementos.svg || !elementos.canvas || !elementos.raiz || !elementos.tipo || !elementos.nome || !elementos.km || !elementos.legenda) {
      return;
    }
    let mapa: ReturnType<typeof criarMapa>;
    try {
      mapa = criarMapa({
        svg: elementos.svg,
        canvas: elementos.canvas,
        topologia,
        fluxos: motor.fluxos,
        cores: lerCoresDoCss(),
        cartao: { raiz: elementos.raiz, tipo: elementos.tipo, nome: elementos.nome, km: elementos.km },
        raizDaLegenda: elementos.legenda,
        rotulos: motor.rotulos,
        aoSelecionar: (f, origem, porTeclado) => selecionar.current(f, origem, porTeclado),
        semRastro: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        rotacao: motor.aoVivo ? ROTACAO_AO_VIVO : undefined,
      });
    } catch (erro) {
      console.error(erro);
      aoErrar(`Erro: ${erro instanceof Error ? erro.message : String(erro)}`);
      return;
    }
    motor.ligarMapa(mapa);

    // Em todo carregamento: confere se alguma rota cruza a borda (o "corte") da projeção. Se cruzar, a linha atravessa o mapa de um
    // lado a outro; isso não impede a página de funcionar, então é um alerta (console e página), não um erro.
    const { rotas, pares, saltos } = mapa.conferirCorte();
    if (saltos > 0) {
      const mensagem = `Atenção: ${saltos} de ${pares} segmentos das ${rotas} rotas cruzam a borda do mapa (as rotas mudaram?). Ajuste ROTACAO em mapa/rotas.ts.`;
      console.warn(mensagem);
      aoAlertar(mensagem);
    }
    motor.iniciar();

    return () => {
      motor.parar();
      motor.desligarMapa();
      mapa.destruir();
    };
  }, [motor, topologia, legenda, aoErrar, aoAlertar]);

  return <AreaDoMapa refs={refs} />;
}

/** Filtro por região: uma caixa por região de destino que existe no JSON. Desligar uma esconde os fluxos dela no mapa; o placar não muda. */
export const FiltroDeRegioes = memo(function FiltroDeRegioes({ regioes, ligadas, aoMudar }: { regioes: string[]; ligadas: ReadonlySet<string>; aoMudar: (regiao: string, ligada: boolean) => void }) {
  return (
    <div className="filtro-regioes" role="group" aria-label="Regiões exibidas no mapa">
      <span className="controle-nome" aria-hidden="true">
        Destinos
      </span>
      <span className="regioes">
        {regioes.map((regiao) => (
          <label className="regiao" key={regiao}>
            <input type="checkbox" checked={ligadas.has(regiao)} onChange={(evento) => aoMudar(regiao, evento.target.checked)} />
            {regiao}
          </label>
        ))}
      </span>
    </div>
  );
});

/**
 * Legenda fixa, sobre o canto do mapa sem rotas (Pacífico Sul). Os ícones dos nós são desenhados pelo mapa com as mesmas formas do mapa
 * (svg[data-forma]); os dois tipos de trecho usam as mesmas classes do mapa.
 */
export const Legenda = memo(function Legenda({ raiz }: { raiz: Ref<HTMLElement> }) {
  return (
    <section className="legenda" id="legenda" ref={raiz} aria-label="Legenda do mapa">
      <h2>Legenda</h2>
      <ul className="lista-legenda">
        <li>
          <span className="icone icone-pulso" aria-hidden="true"></span>Medição (a cor é a situação)
        </li>
        <li>
          <span className="icone icone-timeout" aria-hidden="true">
            &times;
          </span>
          Sem resposta
        </li>
        <li>
          <span className="icone-veredito" aria-hidden="true">
            &#10003; &#10007;
          </span>
          Previsão acertou / errou
        </li>
        <li>
          <svg className="legenda-icone" data-forma="sonda" viewBox="0 0 24 24" aria-hidden="true"></svg>Ponto de medição
        </li>
        <li>
          <svg className="legenda-icone" data-forma="destino" viewBox="0 0 24 24" aria-hidden="true"></svg>Destino
        </li>
        <li className="so-replay">
          <svg className="legenda-icone" data-forma="pop" viewBox="0 0 24 24" aria-hidden="true"></svg>Parada na rota
        </li>
        <li className="so-replay">
          <svg className="legenda-icone" data-forma="aterragem" viewBox="0 0 24 24" aria-hidden="true"></svg>Cabo chega à costa
        </li>
        <li className="so-replay">
          <svg className="legenda-icone" viewBox="0 0 24 24" aria-hidden="true">
            <line className="trecho-linha trecho-terrestre-amostra" x1="1" y1="12" x2="23" y2="12"></line>
          </svg>
          Por terra
        </li>
        <li className="so-replay">
          <svg className="legenda-icone" viewBox="0 0 24 24" aria-hidden="true">
            <line className="trecho-linha trecho-submarino-amostra" x1="1" y1="12" x2="23" y2="12"></line>
          </svg>
          Cabo submarino
        </li>
        <li className="so-ao-vivo">
          <svg className="legenda-icone" viewBox="0 0 24 24" aria-hidden="true">
            <line className="trecho-linha trecho-direto-amostra" x1="1" y1="12" x2="23" y2="12"></line>
          </svg>
          Linha direta (ilustrativa)
        </li>
        <li className="legenda-selo">
          <span className="icone-selo" aria-hidden="true">
            A
          </span>
          Quadradinho = o que o sistema prevê para daqui a 12 min (N = Normal, A = Atenção, P = Problema)
        </li>
      </ul>
    </section>
  );
});
