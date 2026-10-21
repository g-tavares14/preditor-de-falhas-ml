// api.ts: o cliente da API do servidor Go (`/api/previsoes`), usado pelas telas Testar e Histórico. Contrato em
// `servidor/internal/api/swagger/openapi.json`.

import type { Classe } from "../tipos";

/** As 10 colunas que o modelo recebe. Ausente (null) é aceito e chega ao modelo como ausente, nunca como zero. */
export type Entrada = Record<NomeDaColuna, number | null>;

export const NOMES_DAS_COLUNAS = [
  "z_robusto",
  "aumento_pct",
  "jitter_relativo",
  "perda_pct",
  "timeout_atual",
  "n5_timeout",
  "n5_aumento80",
  "n5_moderado",
  "min5_z",
  "media5_z",
] as const;
export type NomeDaColuna = (typeof NOMES_DAS_COLUNAS)[number];

/** O erro no formato RFC 9457 (`application/problem+json`); `errors` só na validação (400). */
export interface Problema {
  title: string;
  status: number;
  detail?: string;
  errors?: Record<string, string[]>;
}

export interface PrevisaoResposta {
  id: number;
  criadaEmUtc: string;
  classe: Classe;
  probabilidades: Record<Classe, number>;
  modeloSha256: string;
}

export interface ItemDoHistorico {
  previsao: PrevisaoResposta;
  entrada: Entrada;
  origem: string;
}

export interface PaginaDePrevisoes {
  pagina: number;
  tamanho: number;
  total: number;
  itens: ItemDoHistorico[];
}

/** Um pedido que a API recusou (ou que nem chegou a ela): `problema` traz o que o servidor explicou, quando explicou. */
export class ErroDaApi extends Error {
  constructor(
    mensagem: string,
    readonly status: number,
    readonly problema: Problema | null,
  ) {
    super(mensagem);
    this.name = "ErroDaApi";
  }
}

async function lerResposta<T>(resposta: Response): Promise<T> {
  if (resposta.ok) {
    return (await resposta.json()) as T;
  }
  let problema: Problema | null = null;
  try {
    problema = (await resposta.json()) as Problema;
  } catch {
    // Corpo que não é JSON (um proxy no meio, por exemplo): fica só o status.
  }
  throw new ErroDaApi(problema?.title ?? `A API respondeu ${resposta.status}.`, resposta.status, problema);
}

async function pedir(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (erro) {
    if (erro instanceof DOMException && erro.name === "AbortError") {
      throw erro; // quem pediu desistiu (saiu da tela): não é falha do servidor
    }
    // Sem rede ou servidor fora: não há resposta para ler.
    throw new ErroDaApi("Não consegui falar com o servidor.", 0, null);
  }
}

/** `origem=formulario` marca no histórico que a previsão veio da tela Testar (e não de um POST direto). */
export async function criarPrevisao(entrada: Entrada, origem: "api" | "formulario" = "formulario"): Promise<PrevisaoResposta> {
  const resposta = await pedir(`/api/previsoes?origem=${origem}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entrada),
  });
  return lerResposta<PrevisaoResposta>(resposta);
}

export async function listarPrevisoes(pagina: number, tamanho: number, sinal?: AbortSignal): Promise<PaginaDePrevisoes> {
  const resposta = await pedir(`/api/previsoes?pagina=${pagina}&tamanho=${tamanho}`, { signal: sinal });
  return lerResposta<PaginaDePrevisoes>(resposta);
}
