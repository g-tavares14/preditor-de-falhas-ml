// aovivo.ts: o modo ao vivo da página (`?ao-vivo`, SPEC-ao-vivo.md).
//
// Lógica pura, sem DOM: roda em Node. A página lê `dados/aovivo.json`, que o serviço (`uv run python -m preditor_analise aovivo`) regrava
// a cada consulta ao RIPE Atlas, no mesmo formato do `replay.json`. O relógio anda em tempo real, ATRASADO `meta.atraso_s`: a API do
// Atlas entrega cada medição uns 100 s depois que ela acontece, e o serviço consulta de minuto em minuto. Com o atraso, quando o
// relógio chega ao instante de uma medição ela já está no arquivo, e o pulso sai na hora certa em vez de em rajada.

import type { Fluxo } from "../tipos";

export const ARQUIVO_AO_VIVO = "/dados/aovivo.json";
export const MENSAGEM_SEM_DADOS_AO_VIVO =
  "Falta o arquivo dados/aovivo.json. Rode antes: uv run python -m preditor_analise aovivo (a primeira consulta leva cerca de 1 minuto depois do baseline).";

/**
 * Se o relógio ficar mais que isto atrás do alvo (aba escondida, computador dormindo), ele PULA em vez de soltar centenas de pulsos de
 * uma vez. Decisão visual; o pulso mais lento dura poucos segundos.
 */
export const SALTO_MAXIMO_S = 120;

/** Se o arquivo não for regravado por tantas consultas seguidas, a página avisa que o serviço parou. */
const CONSULTAS_ATE_AVISAR = 3;

/** O modo ao vivo liga com `?ao-vivo` no endereço (com ou sem valor). */
export function modoAoVivo(busca: string): boolean {
  return new URLSearchParams(busca).has("ao-vivo");
}

/** O instante que o relógio deve marcar agora: a hora real (segundos UTC) menos o atraso. */
export function instanteDoRelogio(agoraEmMs: number, atrasoS: number): number {
  return Math.floor(agoraEmMs / 1000) - atrasoS;
}

/**
 * Os dois JSON têm exatamente os mesmos fluxos, na mesma ordem? (O `f` das medições é a posição na lista: se a lista mudou, o mapa
 * montado não vale mais e a página recarrega.)
 */
export function mesmosFluxos(a: Fluxo[], b: Fluxo[]): boolean {
  return a.length === b.length && a.every((fluxo, i) => fluxo.id === b[i].id);
}

/** "agora mesmo", "há 40 s", "há 3 min", "há 2 h": há quanto tempo o serviço gravou o arquivo. */
export function textoDaIdade(segundos: number): string {
  if (segundos < 10) {
    return "agora mesmo";
  }
  if (segundos < 90) {
    return `há ${Math.round(segundos)} s`;
  }
  if (segundos < 5400) {
    return `há ${Math.round(segundos / 60)} min`;
  }
  return `há ${Math.round(segundos / 3600)} h`;
}

/**
 * O serviço está parado? O arquivo deveria ser regravado a cada consulta (`meta.atualizacao_s` é só a releitura da página; o serviço
 * consulta a cada `intervaloDoServicoS`).
 */
export function servicoParado(idadeS: number, intervaloDoServicoS: number): boolean {
  return idadeS > CONSULTAS_ATE_AVISAR * intervaloDoServicoS;
}
