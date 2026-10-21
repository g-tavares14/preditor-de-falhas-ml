// Paineis.tsx: os painéis de leitura: contadores, "como ler", o placar e o feed das últimas previsões conferidas
// (SPEC-visualizacao.md, "Comportamento da página", item 6). Só mostram o que o motor publicou; nada é calculado aqui.

import { memo } from "react";
import { NOME_DA_CLASSE, TEXTO_ACERTOU, TEXTO_ERROU, formatarPorcentagem } from "../logica/comum";
import { acertou } from "../logica/placar";
import type { Classe, Medicao, MetaDoReplay, ModeloDoReplay } from "../tipos";
import { Chip } from "./Chip";
import { LINHAS_DO_FEED, type ResumoDoPlacar, type ResumoDosContadores } from "./motor";

const CLASSES: Classe[] = ["OK", "RISCO", "FALHA"];

/** Contadores das medições exibidas até o instante do relógio, numa faixa só sob o cartão da conexão. Não recebem foco e não anunciam nada. */
export const Contadores = memo(function Contadores({ contadores, geral }: { contadores: ResumoDosContadores; geral: number }) {
  return (
    <section className="cartao contadores" aria-label="Medições exibidas por situação">
      <h2>Medições até agora</h2>
      <ul className="lista-classes-linha">
        {CLASSES.map((classe) => (
          <li key={classe}>
            <span className={`selo selo-${classe.toLowerCase()}`} aria-hidden="true"></span>
            {NOME_DA_CLASSE[classe]} <span className="numero">{contadores.porClasse[classe]}</span>
          </li>
        ))}
      </ul>
      <p className="resumo">
        <span className="numero">{contadores.total}</span> de <span className="numero">{geral}</span>
        {" "}&middot; sem resposta <span className="numero">{contadores.timeouts}</span>
      </p>
    </section>
  );
});

export const ComoLer = memo(function ComoLer({ aoVivo }: { aoVivo: boolean }) {
  return (
    <section className="cartao como-ler" aria-label="Como ler esta página">
      <h2>Como ler</h2>
      <ol className="passos">
        <li>
          <strong>Medir.</strong> <span>{aoVivo ? "Aparelhos na América Latina" : "Aparelhos no Brasil"}</span> cronometram a ida e volta de uma mensagem até servidores
          no exterior. Cada medição é um pulso no mapa.
        </li>
        <li>
          <strong>Comparar.</strong> Cada conexão é comparada com o próprio normal: <span className="chip chip-ok">Normal</span> habitual,{" "}
          <span className="chip chip-risco">Atenção</span> mais lenta, <span className="chip chip-falha">Problema</span> muito mais lenta ou sem resposta.
        </li>
        <li>
          <strong>Prever.</strong> O sistema prevê a situação de daqui a 12 min e depois confere: &#10003; acertou, &#10007; errou.
        </li>
      </ol>
    </section>
  );
});

const PERIODO_DO_REPLAY =
  "Período de validação: dados que ajudaram a escolher o modelo. O número do relatório vem de outro período, e por isso pode ser um pouco diferente.";

function periodoAoVivo(meta: MetaDoReplay): string {
  return (
    `Ao vivo: pontos de medição que não estão no treino do modelo, lidos na API do RIPE Atlas${meta.janela_h ? ` (últimas ${meta.janela_h} h)` : ""}. ` +
    "Só entram previsões já conferidas (12 min depois); no começo são poucas."
  );
}

function ColunaDoPlacar({ titulo, acertos, conferidas }: { titulo: string; acertos: number; conferidas: number }) {
  return (
    <div className="placar-modelo">
      <h3>{titulo}</h3>
      <p className="placar-pct numero">
        <span>{formatarPorcentagem(acertos, conferidas)}</span>
      </p>
      <p className="placar-numeros numero">
        <span>{acertos}</span> de <span>{conferidas}</span>
      </p>
    </div>
  );
}

/** Quanto o sistema acertou, ao lado do "palpite simples" (a persistência: "tudo igual a agora"). Só entram previsões já conferidas. */
export const Placar = memo(function Placar({ placar, modelo, meta, aoVivo }: { placar: ResumoDoPlacar; modelo: ModeloDoReplay; meta: MetaDoReplay; aoVivo: boolean }) {
  return (
    <section className="cartao placar" aria-label="Quanto o sistema acertou">
      <h2 className="titulo-com-nota">
        <span>Quanto o sistema acertou</span>
        <small>todas as conexões</small>
      </h2>
      <p className="placar-contexto">
        <span>{aoVivo ? periodoAoVivo(meta) : PERIODO_DO_REPLAY}</span> Modelo: <span>{`${modelo.nome}, ${modelo.arvores} árvores`}</span>.
      </p>
      <div className="placar-colunas">
        <ColunaDoPlacar titulo="Nosso sistema" acertos={placar.acertosModelo} conferidas={placar.conferidas} />
        <ColunaDoPlacar titulo="Palpite simples" acertos={placar.acertosPersistencia} conferidas={placar.conferidas} />
      </div>
      <p className="legenda-nota">Palpite simples = &ldquo;tudo igual a agora&rdquo;. Só entram previsões já conferidas.</p>
    </section>
  );
});

interface PropsDoFeed {
  feed: Medicao[];
  rotulos: string[];
  soErros: boolean;
  filtroDeRegioes: boolean;
  /** Clique (ou Enter / Espaço) numa linha: abre o cartão da conexão. `origem` é o botão, para devolver o foco a ele depois. */
  aoSelecionar: (f: number, origem: Element, porTeclado: boolean) => void;
  aoMudarSoErros: (valor: boolean) => void;
}

/** As últimas previsões conferidas: o que o sistema previu → o que aconteceu 12 min depois. Cada linha é um botão. */
export const Feed = memo(function Feed({ feed, rotulos, soErros, filtroDeRegioes, aoSelecionar, aoMudarSoErros }: PropsDoFeed) {
  return (
    <section className="cartao feed-cartao" aria-label="Últimas previsões conferidas">
      <h2 className="titulo-com-nota">
        <span>Últimas previsões conferidas</span>
        <label className="so-erros">
          <input type="checkbox" checked={soErros} onChange={(evento) => aoMudarSoErros(evento.target.checked)} /> só os erros
        </label>
      </h2>
      <p className="legenda-nota">
        o que o sistema previu &rarr; o que aconteceu 12 min depois &middot; &#10003; acertou, &#10007; errou
        {filtroDeRegioes ? <span> &middot; só destinos ligados</span> : null}
      </p>
      <ol className="feed">
        {Array.from({ length: LINHAS_DO_FEED }, (_, i) => {
          const medicao = feed[i];
          return (
            <li key={i}>
              {medicao === undefined ? <button type="button" className="feed-linha feed-vazia" tabIndex={-1} aria-hidden="true" disabled /> : <LinhaDoFeed medicao={medicao} rotulo={rotulos[medicao.f]} aoSelecionar={aoSelecionar} />}
            </li>
          );
        })}
      </ol>
    </section>
  );
});

function LinhaDoFeed({ medicao, rotulo, aoSelecionar }: { medicao: Medicao; rotulo: string; aoSelecionar: PropsDoFeed["aoSelecionar"] }) {
  const ok = acertou(medicao);
  const previsto = medicao.previsto;
  const futuro = medicao.futuro as Classe;
  return (
    <button
      type="button"
      className={`feed-linha${ok ? "" : " feed-erro"}`}
      aria-label={`Ver a conexão ${rotulo}: o sistema previu ${NOME_DA_CLASSE[previsto]}, aconteceu ${NOME_DA_CLASSE[futuro]}, ${ok ? TEXTO_ACERTOU : TEXTO_ERROU}`}
      onClick={(evento) => aoSelecionar(medicao.f, evento.currentTarget, evento.detail === 0)}
    >
      <span className="feed-fluxo" title={rotulo}>
        {rotulo}
      </span>
      <span className="feed-previsto">
        <Chip classe={previsto} />
      </span>
      <span className="feed-real">
        <Chip classe={futuro} />
      </span>
      <span className="feed-marca" title={ok ? TEXTO_ACERTOU : TEXTO_ERROU}>
        {ok ? "✓" : "✗"}
      </span>
    </button>
  );
}
