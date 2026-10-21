// PaginaDoMapa.tsx: a página do mapa, nos dois modos (replay e ao vivo): junta o motor, o mapa e os painéis
// (SPEC-visualizacao.md, SPEC-ao-vivo.md, SPEC-go-react.md).
//
// A ordem dos blocos abaixo é a ordem do Tab e da leitura: primeiro os controles do relógio, depois o mapa (com o filtro de destinos na
// frente dele), o cartão da conexão e, por fim, os painéis da direita (como ler, placar e feed). No computador, o CSS põe o relógio e
// os painéis na coluna da direita; no celular, tudo empilha nesta ordem.

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useLocation } from "react-router";
import type { Topology } from "topojson-specification";
import { ARQUIVO_AO_VIVO, modoAoVivo } from "../logica/aovivo";
import type { Replay } from "../tipos";
import { CartaoDoFluxo } from "./CartaoDoFluxo";
import { carregarJson, useCarga } from "./dados";
import { Cabecalho, Menu } from "./Menu";
import { FiltroDeRegioes, Legenda, Mapa } from "./Mapa";
import type { Motor } from "./motor";
import { ComoLer, Contadores, Feed, Placar } from "./Paineis";
import { Relogio } from "./Relogio";


/** Controles que usam o Espaço para si (apertar o botão, marcar a caixa, abrir a lista): neles o atalho de tocar / pausar não age. A barra de tempo não usa o Espaço, então ali ele toca e pausa. */
const USAM_O_ESPACO = 'button, select, textarea, a[href], [role="button"], input:not([type="range"])';

/** Ao vivo: de quanto em quanto tempo a página relê o arquivo (o `meta.atualizacao_s` do JSON manda; este é o padrão). */
const ATUALIZACAO_PADRAO_S = 30;

/** A rota "/" nos dois modos: o ao vivo liga com `?ao-vivo`. Trocar de modo remonta a página inteira (cada modo é uma página). */
export function PaginaDoMapa() {
  const aoVivo = modoAoVivo(useLocation().search);
  return <PaginaDoModo key={aoVivo ? "ao-vivo" : "replay"} aoVivo={aoVivo} />;
}

function PaginaDoModo({ aoVivo }: { aoVivo: boolean }) {
  const [erroDeExecucao, setErroDeExecucao] = useState<string | null>(null);
  const aoErrar = useCallback((mensagem: string) => setErroDeExecucao(mensagem), []);
  const carga = useCarga(aoVivo, aoErrar);

  // O CSS esconde barra, velocidades e botão no modo ao vivo (e a legenda de cabos) pela classe `ao-vivo` no <body>.
  useEffect(() => {
    document.body.classList.toggle("ao-vivo", aoVivo);
    return () => document.body.classList.remove("ao-vivo");
  }, [aoVivo]);

  if (carga.tipo !== "pronto") {
    return <CascaDeCarga aoVivo={aoVivo} carga={carga} />;
  }
  return <Pagina aoVivo={aoVivo} replay={carga.replay} topologia={carga.topologia} motor={carga.motor} erro={erroDeExecucao} aoErrar={aoErrar} />;
}

/** Enquanto carrega (ou se falhar): o menu, o cabeçalho e a mensagem, no lugar do mapa. */
function CascaDeCarga({ aoVivo, carga }: { aoVivo: boolean; carga: { tipo: "carregando" } | { tipo: "aguardando"; mensagem: string } | { tipo: "erro"; mensagem: string } }) {
  return (
    <div className="app">
      <Menu aoVivo={aoVivo} />
      <div className="conteudo">
        <Cabecalho avisoAoVivo={null} />
        <main className="palco">
          <div className="coluna-mapa">
            <section className="cartao cartao-mapa" aria-label="Mapa-múndi com as medições de cada conexão">
              {carga.tipo === "carregando" ? (
                <p className="status" role="status">
                  Carregando a simulação...
                </p>
              ) : (
                <p className="erro" role="alert">
                  {carga.mensagem}
                </p>
              )}
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}

interface PropsDaPagina {
  aoVivo: boolean;
  replay: Replay;
  topologia: Topology;
  motor: Motor;
  erro: string | null;
  aoErrar: (mensagem: string) => void;
}

function Pagina({ aoVivo, replay, topologia, motor, erro, aoErrar }: PropsDaPagina) {
  const inst = useSyncExternalStore(motor.inscrever, motor.lerInstantaneo);
  const [alerta, setAlerta] = useState<string | null>(null);
  const legenda = useRef<HTMLElement>(null);
  const cartaoRaiz = useRef<HTMLElement>(null);
  /** O elemento que abriu o cartão (selo, linha do feed ou lista): o Esc devolve o foco a ele. */
  const origemDoFoco = useRef<Element | null>(null);

  /**
   * Abre o cartão do fluxo `f` (ou fecha, com null). `origem` é o elemento que o abriu; `porTeclado`: o foco vai para o cartão, para o
   * leitor de tela lê-lo e o Esc o fechar. O cartão sempre existe no DOM (só muda o conteúdo), então o foco já cai num elemento visível.
   */
  const selecionar = useCallback(
    (f: number, origem: Element, porTeclado: boolean) => {
      origemDoFoco.current = origem;
      motor.selecionar(f);
      if (porTeclado) {
        cartaoRaiz.current?.focus();
      }
      // Em tela estreita o cartão fica abaixo do mapa: leva-o à vista, sem rolar se já está inteiro na tela.
      cartaoRaiz.current?.scrollIntoView({ block: "nearest" });
    },
    [motor],
  );

  /**
   * O elemento visível ao qual o foco deve voltar quando o cartão fecha: quem o abriu; se ele sumiu (região desligada, por exemplo), o
   * selo do fluxo; se nem esse existe, nenhum.
   */
  const elementoParaDevolverOFoco = useCallback(
    (f: number): Element | null => {
      const visivel = (elemento: Element | null): elemento is Element => elemento !== null && elemento.isConnected && elemento.getClientRects().length > 0;
      if (visivel(origemDoFoco.current)) {
        return origemDoFoco.current;
      }
      const selo = motor.alvoDoSelo(f);
      return visivel(selo) ? selo : null;
    },
    [motor],
  );

  /** Fecha o cartão (Esc ou o botão ×). Se o foco estava nele (ou se perdeu com o clique no ×), volta para quem o abriu. */
  const fecharCartao = useCallback(() => {
    const f = motor.lerInstantaneo().selecionado;
    if (f === null) {
      return;
    }
    const foco = document.activeElement;
    const focoNoCartao = foco === document.body || (cartaoRaiz.current?.contains(foco) ?? false);
    motor.selecionar(null);
    motor.anunciar("Detalhes da conexão fechados.");
    const destino = focoNoCartao ? elementoParaDevolverOFoco(f) : null;
    (destino as HTMLElement | null)?.focus();
  }, [motor, elementoParaDevolverOFoco]);

  // Atalhos de teclado da página: Esc fecha o cartão do fluxo (e devolve o foco a quem o abriu); Espaço toca e pausa. As setas e Enter
  // dos selos ficam em mapa/foco.ts e mapa/selos.ts.
  useEffect(() => {
    function aoApertar(evento: KeyboardEvent): void {
      if (evento.defaultPrevented) {
        return; // alguém (um selo, a barra) já tratou a tecla
      }
      if (evento.key === "Escape" && motor.lerInstantaneo().selecionado !== null) {
        fecharCartao();
      }
      const semModificador = !evento.altKey && !evento.ctrlKey && !evento.metaKey && !evento.shiftKey;
      const alvo = evento.target instanceof Element ? evento.target : null;
      if (evento.key === " " && !evento.repeat && semModificador && !alvo?.closest(USAM_O_ESPACO)) {
        evento.preventDefault(); // Espaço não rola a página
        motor.alternarTocar();
      }
    }
    document.addEventListener("keydown", aoApertar);
    return () => document.removeEventListener("keydown", aoApertar);
  }, [motor, fecharCartao]);

  // Ao vivo: relê o arquivo de tempos em tempos. Se a lista de conexões mudou (o serviço foi recomeçado), recarrega a página.
  useEffect(() => {
    if (!aoVivo) {
      return;
    }
    const controle = new AbortController();
    async function reler(): Promise<void> {
      let novo: Replay;
      try {
        novo = await carregarJson<Replay>(ARQUIVO_AO_VIVO, true, controle.signal);
      } catch (erro) {
        if (!controle.signal.aborted) {
          console.warn(erro); // sem arquivo agora: o selo passa a avisar que os dados envelhecem
        }
        return;
      }
      try {
        if (!motor.substituirDados(novo)) {
          window.location.reload();
        }
      } catch (erro) {
        aoErrar(`Erro: ${erro instanceof Error ? erro.message : String(erro)}`);
      }
    }
    const id = setInterval(() => void reler(), (replay.meta.atualizacao_s ?? ATUALIZACAO_PADRAO_S) * 1000);
    return () => {
      clearInterval(id);
      controle.abort();
    };
  }, [aoVivo, motor, replay.meta.atualizacao_s, aoErrar]);

  const escolher = useCallback((f: number, origem: Element) => selecionar(f, origem, true), [selecionar]);
  const mudarSoErros = useCallback((valor: boolean) => motor.definirSoErros(valor), [motor]);
  const mudarRegiao = useCallback((regiao: string, ligada: boolean) => motor.alternarRegiao(regiao, ligada), [motor]);

  return (
    <>
      <div className="app">
        <Menu aoVivo={aoVivo} />
        <div className="conteudo">
          <Cabecalho avisoAoVivo={aoVivo ? replay.meta.aviso : null} />
          <main className="palco">
            <Relogio motor={motor} inst={inst} meta={replay.meta} />

            <div className="coluna-mapa">
              <section className="cartao cartao-mapa" aria-label="Mapa-múndi com as medições de cada conexão">
                <FiltroDeRegioes regioes={motor.todasAsRegioes} ligadas={inst.regioesLigadas} aoMudar={mudarRegiao} />
                <Mapa motor={motor} topologia={topologia} legenda={legenda} aoSelecionar={selecionar} aoErrar={aoErrar} aoAlertar={setAlerta} />
                <Legenda raiz={legenda} />
                {erro !== null ? (
                  <p className="erro" role="alert">
                    {erro}
                  </p>
                ) : null}
                {alerta !== null ? (
                  <p className="alerta" role="status">
                    {alerta}
                  </p>
                ) : null}
              </section>

              <CartaoDoFluxo cartao={inst.cartao} fluxos={motor.fluxos} rotulos={motor.rotulos} aoFechar={fecharCartao} aoEscolher={escolher} raiz={cartaoRaiz} />
              <Contadores contadores={inst.contadores} geral={motor.totalDeMedicoes} />
            </div>

            <div className="painel">
              <ComoLer aoVivo={aoVivo} />
              <Placar placar={inst.placar} modelo={motor.modelo} meta={replay.meta} aoVivo={aoVivo} />
              <Feed feed={inst.feed} rotulos={motor.rotulos} soErros={inst.soErros} filtroDeRegioes={inst.filtroDeRegioes} aoSelecionar={selecionar} aoMudarSoErros={mudarSoErros} />
            </div>
          </main>
        </div>
      </div>

      {/* Aviso para leitor de tela, escrito só quando a simulação para ou recomeça, quando acaba ou quando um fluxo é aberto (nunca a cada
          quadro). Fica fora da tela. */}
      <p className="so-leitor" id="anuncio" role="status" aria-live="polite">
        {inst.anuncio}
      </p>
    </>
  );
}
