// dados.ts: carrega o JSON do replay (ou do ao vivo) e o mapa-base, e cria o motor (SPEC-visualizacao.md, SPEC-ao-vivo.md).

import { useEffect, useState } from "react";
import type { Topology } from "topojson-specification";
import { ARQUIVO_AO_VIVO, MENSAGEM_SEM_DADOS_AO_VIVO } from "../logica/aovivo";
import { DICA_REPLAY } from "../logica/tempo";
import type { Replay } from "../tipos";
import { Motor } from "./motor";

export const ARQUIVO_REPLAY = "/dados/replay.json";
const ARQUIVO_MAPA = "/mapa/countries-110m.json";
const MENSAGEM_SEM_MAPA = "Falta o arquivo mapa/countries-110m.json (ver web/public/mapa/README.md)";
/** Ao vivo, enquanto o arquivo não existe (o serviço ainda está no baseline), a página tenta de novo a cada tanto. */
const ESPERA_SEM_DADOS_MS = 10000;

/**
 * `revalidar` (`no-cache`) = o navegador pergunta ao servidor se o arquivo mudou: só o `aovivo.json`, regravado a cada minuto. O resto
 * usa o cache normal (o servidor manda `max-age`), para trocar de modo sem rebaixar tudo.
 */
export async function carregarJson<T>(url: string, revalidar = false, sinal?: AbortSignal): Promise<T> {
  const resposta = await fetch(url, { signal: sinal, ...(revalidar ? { cache: "no-cache" as const } : {}) });
  if (!resposta.ok) {
    throw new Error(`${url}: HTTP ${resposta.status}`);
  }
  return (await resposta.json()) as T;
}

export type Carga =
  | { tipo: "carregando" }
  /** Ao vivo, o arquivo ainda não existe: a página espera e mostra o motivo. */
  | { tipo: "aguardando"; mensagem: string }
  | { tipo: "erro"; mensagem: string }
  | { tipo: "pronto"; replay: Replay; topologia: Topology; motor: Motor };

function esperar(ms: number, sinal: AbortSignal): Promise<void> {
  return new Promise((resolver) => {
    const id = setTimeout(resolver, ms);
    sinal.addEventListener("abort", () => (clearTimeout(id), resolver()), { once: true });
  });
}

/**
 * Carrega os dados e cria o motor. `aoErrar` recebe os erros que acontecem DEPOIS (no laço de animação e na releitura do ao vivo):
 * a página os mostra no lugar do mapa, sem derrubar o resto.
 */
export function useCarga(aoVivo: boolean, aoErrar: (mensagem: string) => void): Carga {
  const [carga, setCarga] = useState<Carga>({ tipo: "carregando" });

  useEffect(() => {
    const controle = new AbortController();
    const { signal } = controle;

    async function carregar(): Promise<void> {
      // O mapa-base começa a baixar já, junto com os dados (antes um esperava o outro).
      const promessaTopologia = carregarJson<Topology>(ARQUIVO_MAPA, false, signal).catch((erro: unknown) => {
        if (!signal.aborted) {
          console.error(erro);
        }
        return null;
      });

      let replay: Replay | null = null;
      while (replay === null && !signal.aborted) {
        try {
          replay = await carregarJson<Replay>(aoVivo ? ARQUIVO_AO_VIVO : ARQUIVO_REPLAY, aoVivo, signal);
        } catch (erro) {
          if (signal.aborted) {
            return;
          }
          console.error(erro);
          const mensagem = aoVivo ? MENSAGEM_SEM_DADOS_AO_VIVO : DICA_REPLAY;
          if (!aoVivo) {
            setCarga({ tipo: "erro", mensagem });
            return;
          }
          // Ao vivo o arquivo só existe depois da primeira consulta do serviço: a página espera, em vez de ficar parada no erro.
          setCarga({ tipo: "aguardando", mensagem });
          await esperar(ESPERA_SEM_DADOS_MS, signal);
        }
      }
      const topologia = await promessaTopologia;
      if (signal.aborted || replay === null) {
        return;
      }
      if (topologia === null) {
        setCarga({ tipo: "erro", mensagem: MENSAGEM_SEM_MAPA });
        return;
      }
      try {
        const motor = new Motor({ replay, aoVivo, aoErrar });
        setCarga({ tipo: "pronto", replay, topologia, motor });
      } catch (erro) {
        console.error(erro);
        setCarga({ tipo: "erro", mensagem: `Erro: ${erro instanceof Error ? erro.message : String(erro)}` });
      }
    }

    void carregar();
    return () => controle.abort();
  }, [aoVivo, aoErrar]);

  return carga;
}
