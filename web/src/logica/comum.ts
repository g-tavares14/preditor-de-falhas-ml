// comum.ts: pequenas funções de texto usadas por mais de um componente da página.
//
// Nada aqui calcula métrica nem rótulo: só formata o que já vem no JSON.
//
// Linguagem para quem não é da área: o JSON e o CSS continuam com os códigos do projeto (OK, RISCO, FALHA); só o que aparece na tela é
// traduzido, e a tradução mora aqui, em um lugar só.

import type { Classe, Fluxo } from "../tipos";

export const TEXTO_ACERTOU = "Acertou";
export const TEXTO_ERROU = "Errou";

/**
 * Como cada classe aparece na tela. A cor e o texto andam juntos (nunca só cor). "Problema" não quer dizer "fora do ar": a classe FALHA
 * inclui também a conexão que ficou muito mais lenta que o normal dela (RFC §8.4, linhas 1 a 3).
 */
export const NOME_DA_CLASSE: Record<Classe, string> = { OK: "Normal", RISCO: "Atenção", FALHA: "Problema" };
/** A letra do quadradinho de previsão no mapa. */
export const SIGLA_DA_CLASSE: Record<Classe, string> = { OK: "N", RISCO: "A", FALHA: "P" };

/** Países do dataset por extenso (só para exibir; o JSON traz o código de duas letras). */
const NOME_DO_PAIS: Record<string, string> = {
  BR: "Brasil", DE: "Alemanha", JP: "Japão", PT: "Portugal", SG: "Singapura", US: "Estados Unidos",
  // Origens do modo ao vivo (América Latina, SPEC-ao-vivo.md).
  AR: "Argentina", BO: "Bolívia", CL: "Chile", CO: "Colômbia", CR: "Costa Rica", EC: "Equador", MX: "México",
  PA: "Panamá", PE: "Peru", PY: "Paraguai", UY: "Uruguai", VE: "Venezuela",
};

export function nomeDoPais(codigo: string): string {
  return NOME_DO_PAIS[codigo] ?? codigo;
}

/** A sonda (primeiro campo do `fluxo_id`) e a cidade do destino (último nó da rota, escrito como "Cidade (dst_addr)"). */
export function detalhesDoFluxo(fluxo: Fluxo): { sonda: string; cidade: string } {
  const ultimoTrecho = fluxo.trechos[fluxo.trechos.length - 1];
  return {
    sonda: fluxo.id.split("|")[0],
    cidade: ultimoTrecho.nos[ultimoTrecho.nos.length - 1].nome.split(" (")[0],
  };
}

/** O país onde fica o ponto de medição: o replay tem só sondas do Brasil (sem `origem_pais` no JSON); o modo ao vivo traz o país. */
export function paisDeOrigem(fluxo: Fluxo): string {
  return nomeDoPais(fluxo.origem_pais ?? "BR");
}

/** "Ponto 6349 → Frankfurt" (replay: a sonda é sempre do Brasil) ou "Ponto 1234 (Chile) → Lisboa" (ao vivo). */
export function rotuloDoFluxo(fluxo: Fluxo): string {
  const { sonda, cidade } = detalhesDoFluxo(fluxo);
  return fluxo.origem_pais === undefined ? `Ponto ${sonda} → ${cidade}` : `Ponto ${sonda} (${paisDeOrigem(fluxo)}) → ${cidade}`;
}

/** "2026-09-23T20:09:58.000Z" vira a data (dia/mês/ano) e a hora separadas, sempre em UTC (a hora real da medição). */
export function formatarInstante(segundos: number): { data: string; hora: string } {
  const iso = new Date(segundos * 1000).toISOString();
  return { data: `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`, hora: iso.slice(11, 19) };
}

/** "2026-09-23 20:09:57 UTC": a data e a hora da barra de tempo, como o leitor de tela as lê. */
export function textoDoInstante(segundos: number): string {
  const { data, hora } = formatarInstante(segundos);
  return `${data} ${hora} UTC`;
}

/** "82,9 %" (uma casa, vírgula); sem conferidas ainda, um traço. É só a razão entre dois contadores do placar. */
export function formatarPorcentagem(acertos: number, conferidas: number): string {
  if (conferidas === 0) {
    return "--";
  }
  const pct = (100 * acertos) / conferidas;
  return `${pct.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}
