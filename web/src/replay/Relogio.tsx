// Relogio.tsx: o relógio e os controles da simulação: hora, tocar / pausar, barra de tempo e velocidade
// (SPEC-visualizacao.md). O relógio de verdade mora no motor; aqui só se mostra o instantâneo e se chamam as ações dele.

import { memo, useEffect, useState } from "react";
import { servicoParado, textoDaIdade } from "../logica/aovivo";
import { formatarInstante } from "../logica/comum";
import type { MetaDoReplay } from "../tipos";
import { NOMES_DAS_VELOCIDADES, VELOCIDADES, type Instantaneo, type Motor } from "./motor";

const ATUALIZACAO_DO_SELO_MS = 1000;

function textoDoBotao(inst: Instantaneo): string {
  if (inst.terminou) {
    return "Reiniciar";
  }
  return inst.tocando ? "Pausar" : "Tocar";
}

/** A faixa "ao vivo" do relógio: há quanto tempo o serviço gravou o arquivo, e o aviso de que ele pode ter parado. */
function SeloAoVivo({ geradoEmS, intervaloDoServicoS }: { geradoEmS: number | null; intervaloDoServicoS: number }) {
  const [agora, setAgora] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setAgora(Date.now()), ATUALIZACAO_DO_SELO_MS);
    return () => clearInterval(id);
  }, []);

  const idade = Math.max(0, agora / 1000 - (geradoEmS ?? agora / 1000));
  const parado = servicoParado(idade, intervaloDoServicoS);
  return (
    <p className={`ao-vivo-selo so-ao-vivo${parado ? " ao-vivo-parado" : ""}`} id="ao-vivo-selo" role="status">
      {parado ? `● O serviço parou? Dados de ${textoDaIdade(idade)}. Rode: uv run python -m preditor_analise aovivo` : `● Ao vivo · dados de ${textoDaIdade(idade)}`}
    </p>
  );
}

interface Props {
  motor: Motor;
  inst: Instantaneo;
  meta: MetaDoReplay;
}

export const Relogio = memo(function Relogio({ motor, inst, meta }: Props) {
  const { data, hora } = formatarInstante(inst.agora);
  const barra = motor.barra;
  // A barra acompanha o relógio, menos enquanto o ponteiro a segura (senão o relógio brigaria com a mão). No fim do replay o polegar
  // vai para o fim da barra: o `max` dela fica até um passo depois do fim (ver `Motor.barra`), e o valor do relógio cairia no passo
  // anterior, com o polegar "voltando" alguns segundos depois de `End` ou de arrastar até o fim.
  const [arrastando, setArrastando] = useState(false);
  const [valorDaMao, setValorDaMao] = useState(barra.min);
  const valor = arrastando ? valorDaMao : inst.terminou ? barra.max : Math.floor(inst.agora);

  const titulo = motor.aoVivo ? "Relógio ao vivo " : "Relógio da simulação ";
  const nota = motor.aoVivo ? `· hora UTC, ${Math.round((meta.atraso_s ?? 0) / 60)} min atrás da hora real` : "· hora UTC (Brasília + 3 h)";

  return (
    <section className="cartao relogio" aria-label="Relógio e controles da simulação">
      <h2 id="relogio-titulo">
        {titulo}
        <span className="relogio-velocidade" id="relogio-nota">
          {nota}
        </span>
      </h2>
      <div className="relogio-linha">
        <div>
          <p className="relogio-data numero">{data}</p>
          <p className="relogio-hora numero">{hora}</p>
        </div>
        <div className="relogio-controle">
          <button type="button" className="botao" id="botao-tocar" aria-keyshortcuts="Space" title="Tocar ou pausar (barra de espaço)" onClick={() => motor.alternarTocar()}>
            {textoDoBotao(inst)}
          </button>
        </div>
      </div>
      {motor.aoVivo ? <SeloAoVivo geradoEmS={inst.geradoEmS} intervaloDoServicoS={motor.intervaloDoServicoS} /> : null}
      <input
        type="range"
        className="barra"
        id="barra-tempo"
        min={barra.min}
        max={barra.max}
        step={barra.passo}
        value={valor}
        aria-label="Posição no tempo da simulação"
        aria-valuetext={inst.textoDaBarra}
        onChange={(evento) => {
          const novo = Number(evento.target.value);
          setValorDaMao(novo);
          motor.irParaInstante(novo);
        }}
        onPointerDown={() => setArrastando(true)}
        onPointerUp={() => setArrastando(false)}
        onPointerCancel={() => setArrastando(false)}
        onBlur={() => setArrastando(false)}
      />
      <div className="controle-linha" role="group" aria-label="Velocidade da simulação">
        <span className="controle-nome" aria-hidden="true">
          Velocidade
        </span>
        <span className="velocidades">
          {VELOCIDADES.map((velocidade) => (
            <button
              key={velocidade}
              type="button"
              className="botao-velocidade"
              aria-pressed={inst.velocidade === velocidade}
              title={`${velocidade} vezes a velocidade real: 1 minuto na tela = ${velocidade} minutos da simulação`}
              onClick={() => motor.definirVelocidade(velocidade)}
            >
              {NOMES_DAS_VELOCIDADES[velocidade]}
            </button>
          ))}
        </span>
      </div>
    </section>
  );
});
