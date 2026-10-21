// Menu.tsx: a barra lateral que troca entre os dois modos da página, e o cabeçalho com o aviso fixo.
//
// Replay = os dados do projeto (de onde o modelo aprendeu e foi conferido); Ao vivo = o modelo em pontos de medição que ele nunca viu.
// São dois modos da mesma rota (o ao vivo é `?ao-vivo`), por isso são links. O texto é fixo: nenhum script o altera.

import { memo } from "react";
import { Link } from "react-router";

export const Menu = memo(function Menu({ aoVivo }: { aoVivo: boolean }) {
  return (
    <nav className="menu" aria-label="Modos da página">
      <p className="menu-titulo">Modos</p>
      <Link className="menu-item" to="/" aria-current={aoVivo ? undefined : "page"}>
        <span className="menu-nome">Replay</span>
        <span className="menu-quem">O que o modelo aprendeu</span>
        <span className="menu-texto">Medições gravadas em setembro de 2026, de pontos do Brasil: os mesmos pontos do treino, em outro período.</span>
      </Link>
      <Link className="menu-item" to={{ pathname: "/", search: "?ao-vivo" }} aria-current={aoVivo ? "page" : undefined}>
        <span className="menu-nome">
          <span className="menu-ponto" aria-hidden="true"></span>Ao vivo
        </span>
        <span className="menu-quem">O modelo no mundo real</span>
        <span className="menu-texto">Medições de agora, de pontos da América Latina que o modelo nunca viu.</span>
      </Link>
      <p className="menu-nota">Dois testes diferentes: o replay mostra o modelo onde ele aprendeu; o ao vivo mostra se ele funciona fora dali.</p>
    </nav>
  );
});

/** O aviso do replay; ao vivo vem do JSON (`meta.aviso`): a rota é uma linha direta, e o aviso diz isso. */
const AVISO_DO_REPLAY = "Rota ilustrativa: os cabos existem, mas o caminho de cada conexão é simulado.";

export const Cabecalho = memo(function Cabecalho({ avisoAoVivo }: { avisoAoVivo: string | null }) {
  return (
    <header className="cabecalho">
      <div className="titulo">
        <h1>Preditor de falhas de rede</h1>
        <p className="subtitulo">Prevendo problemas de conexão entre países, 12 minutos antes</p>
      </div>
      <p className="aviso" id="aviso" role="note">
        {avisoAoVivo ?? AVISO_DO_REPLAY}
      </p>
    </header>
  );
});
