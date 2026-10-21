// CartaoDoFluxo.tsx: o cartão da conexão selecionada (SPEC-visualizacao.md, "Comportamento da página", item 6, último ponto).
//
// Mostra, em palavras simples, a rota da conexão, a última medição dela até o instante do relógio e a última previsão que o relógio já
// conferiu. Não calcula métrica: tudo já vem no JSON.

import { memo, type Ref } from "react";
import { TEXTO_ACERTOU, TEXTO_ERROU, detalhesDoFluxo, formatarInstante, nomeDoPais, paisDeOrigem } from "../logica/comum";
import { acertou } from "../logica/placar";
import { ehTimeout } from "../logica/tempo";
import type { Classe, Fluxo, Medicao } from "../tipos";
import { Chip } from "./Chip";
import type { DadosDoCartao } from "./motor";

const SEM_FUTURO = "sem como conferir (faltou medição depois)";
const SEM_CONFERIDA = "nenhuma previsão conferida ainda";

/** "123,5 ms" ou "sem resposta" (a medição em que nenhum pacote voltou). */
function textoDoRtt(medicao: Medicao): string {
  return ehTimeout(medicao) ? "sem resposta" : `${(medicao.rtt as number).toLocaleString("pt-BR", { maximumFractionDigits: 1, useGrouping: false })} ms`;
}

/**
 * Situação da previsão da ÚLTIMA medição da conexão. O cartão não adianta o futuro: o `futuro` dela só aparece na linha "última
 * previsão conferida", depois que o relógio passa do `t_futuro`. A última medição que já aconteceu sempre tem o futuro adiante (ele é a
 * 3ª medição seguinte, que ainda não aconteceu), então aqui só há "aguardando" ou "sem futuro".
 */
function textoDaSituacao(medicao: Medicao | null): string {
  if (medicao === null) {
    return "ainda sem medição neste instante";
  }
  if (!medicao.conferivel) {
    return SEM_FUTURO;
  }
  return `será conferida às ${formatarInstante(medicao.t_futuro as number).hora} (UTC)`;
}

function numeroEmMs(valor: number): string {
  return `${valor.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ms`;
}

/** A parte do cartão que só muda quando se escolhe outra conexão: a rota (ponto de medição, destino, cabos, km) e os tempos de referência. */
function RotaDoCartao({ fluxo, aoFechar }: { fluxo: Fluxo; aoFechar: () => void }) {
  const { sonda, cidade } = detalhesDoFluxo(fluxo);
  const trechos = fluxo.trechos.map((trecho) => trecho.nome).join(" → ");
  const pais = nomeDoPais(fluxo.pais);
  const minimo = numeroEmMs(fluxo.rtt_minimo_ms);
  const mediana = fluxo.mediana_ms === null ? "sem referência" : numeroEmMs(fluxo.mediana_ms);
  return (
    <>
      <button type="button" className="fluxo-fechar" aria-label="Fechar os detalhes da conexão" title="Fechar (Esc)" onClick={aoFechar}>
        &times;
      </button>
      <div className="fluxo-rota">
        {/* "Singapura", não "Singapura, Singapura" */}
        <h2>{`Ponto ${sonda} (${paisDeOrigem(fluxo)}) → ${cidade === pais ? cidade : `${cidade}, ${pais}`}`}</h2>
        <p className="fluxo-opcao">
          <span>{`Rota ilustrativa: ${fluxo.opcao}`}</span> &middot; <span className="numero">{`${Math.round(fluxo.km)} km`}</span>
        </p>
        <p className="fluxo-trechos" title={trechos}>{`Passa por: ${trechos}`}</p>
        <p className="fluxo-rtt">{`mínimo ${minimo} × normal ${mediana}`}</p>
        <p className="fluxo-nota">tempo de ida e volta de uma mensagem: o mínimo que a física permite nessa rota &times; o tempo normal medido</p>
      </div>
    </>
  );
}

/** A previsão mais recente da conexão que o relógio já conferiu: a hora (UTC) em que foi feita, o que o sistema previu, o que aconteceu e o resultado (✓ Acertou ou ✗ Errou, com texto e símbolo: nunca só cor). */
function Conferida({ medicao }: { medicao: Medicao | null }) {
  if (medicao === null) {
    return <p className="fluxo-conferida">{SEM_CONFERIDA}</p>;
  }
  const ok = acertou(medicao);
  return (
    <p className={`fluxo-conferida ${ok ? "fluxo-acertou" : "fluxo-errou"}`}>
      <span className="numero">{formatarInstante(medicao.t).hora} </span>
      previu <Chip classe={medicao.previsto} />, aconteceu <Chip classe={medicao.futuro as Classe} />
      {` ${ok ? "✓" : "✗"} ${ok ? TEXTO_ACERTOU : TEXTO_ERROU}`}
    </p>
  );
}

function MedicaoDoCartao({ dados }: { dados: DadosDoCartao }) {
  const { medicao, conferida } = dados;
  return (
    <div className="fluxo-medicao">
      <h3>
        Última medição <span className="numero">{medicao === null ? "--" : `${formatarInstante(medicao.t).hora} UTC`}</span>
      </h3>
      <p>
        Tempo de resposta <span className="numero">{medicao === null ? "--" : textoDoRtt(medicao)}</span>
      </p>
      <p>
        Situação agora <span>{medicao === null ? "--" : <Chip classe={medicao.atual} />}</span>
      </p>
      <p>
        Previsão para daqui a 12 min <span>{medicao === null ? "--" : <Chip classe={medicao.previsto} />}</span>
      </p>
      <p className="fluxo-situacao">{textoDaSituacao(medicao)}</p>
      <h3>Última previsão conferida</h3>
      <Conferida medicao={conferida} />
    </div>
  );
}

interface Props {
  cartao: DadosDoCartao | null;
  fluxos: Fluxo[];
  rotulos: string[];
  /** Esc, o botão × ou (pelo pai) o Esc do teclado. */
  aoFechar: () => void;
  /** A lista "Ou escolha uma conexão": abre o cartão sem usar o mapa. */
  aoEscolher: (f: number, origem: Element) => void;
  /** O cartão recebe o foco (tabindex -1) quando abre por teclado. */
  raiz: Ref<HTMLElement>;
}

/**
 * Fica sob o mapa, sempre com a mesma altura no computador, para a página não pular quando ele abre ou fecha. A uma conexão
 * selecionada corresponde `cartao`; sem seleção, mostra a lista para escolher uma (o toque e o teclado no mapa são difíceis em tela
 * pequena, e o leitor de tela anuncia a lista inteira).
 */
export const CartaoDoFluxo = memo(function CartaoDoFluxo({ cartao, fluxos, rotulos, aoFechar, aoEscolher, raiz }: Props) {
  const f = cartao === null ? null : cartao.f;
  return (
    <section className="cartao fluxo-cartao" id="fluxo-cartao" ref={raiz} tabIndex={-1} aria-label={f === null ? "Conexão selecionada" : `Conexão selecionada: ${rotulos[f]}`}>
      {cartao === null ? (
        <div className="fluxo-vazio">
          <p>Nenhuma conexão selecionada. Clique num quadradinho de previsão, ao lado de um destino no mapa, para ver os detalhes dela.</p>
          <label className="escolha-fluxo">
            <span>Ou escolha uma conexão</span>
            {/* Sempre em "Escolher...": o cartão é que mostra a conexão aberta. Controlado com value="" ele volta sozinho. */}
            <select value="" onChange={(evento) => evento.target.value !== "" && aoEscolher(Number(evento.target.value), evento.target)}>
              <option value="">Escolher...</option>
              {rotulos.map((rotulo, i) => (
                <option key={i} value={i}>
                  {rotulo}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : (
        <div className="fluxo-corpo">
          <RotaDoCartao fluxo={fluxos[cartao.f]} aoFechar={aoFechar} />
          <MedicaoDoCartao dados={cartao} />
        </div>
      )}
    </section>
  );
});
