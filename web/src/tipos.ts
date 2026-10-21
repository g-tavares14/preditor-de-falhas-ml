// tipos.ts: o formato do `replay.json` (e do `aovivo.json`, que é o mesmo formato), como a página o lê.
//
// O JSON é gerado pelo Python (`uv run python -m preditor_analise replay`). Os tipos descrevem só o que a página usa; a conferência
// de que o arquivo de fato tem esse formato é `validarReplay` (logica/tempo.ts), que roda no carregamento.

/** As classes do projeto. O JSON e o CSS usam estes códigos; só o texto da tela é traduzido (logica/comum.ts). */
export type Classe = "OK" | "RISCO" | "FALHA";

/** [longitude, latitude] no JSON; [x, y] depois de projetado no mapa. */
export type Ponto = [number, number];

export type TipoDeTrecho = "terrestre" | "submarino" | "direto";
export type TipoDeNo = "sonda" | "pop" | "aterragem" | "destino";

export interface NoDaRota {
  tipo: TipoDeNo;
  nome: string;
  ponto: Ponto;
}

export interface Trecho {
  tipo: TipoDeTrecho;
  nome: string;
  km: number;
  caminho: Ponto[];
  nos: NoDaRota[];
}

export interface Fluxo {
  id: string; // `prb_id|dst_addr|msm_id`
  regiao: string;
  pais: string;
  opcao: string;
  km: number;
  rtt_minimo_ms: number;
  mediana_ms: number | null;
  /** Só no modo ao vivo: o país do ponto de medição (no replay é sempre o Brasil). */
  origem_pais?: string;
  trechos: Trecho[];
}

export interface Medicao {
  f: number; // posição do fluxo em `fluxos`
  t: number; // segundos UTC desde 1970
  rtt: number | null;
  timeout: 0 | 1;
  atual: Classe;
  previsto: Classe;
  futuro: Classe | null;
  conferivel: boolean;
  t_futuro: number | null;
}

/** Uma medição conferível: o `futuro` e o `t_futuro` existem. */
export type MedicaoConferivel = Medicao & { futuro: Classe; t_futuro: number };

export interface ModeloDoReplay {
  nome: string;
  familia: string;
  arvores: number;
  parametros?: Record<string, unknown>;
  sha256?: string;
  colunas?: string[];
}

export interface MetaDoReplay {
  bloco?: string;
  inicio?: string;
  fim?: string;
  classes: Classe[];
  aviso: string;
  // Só no modo ao vivo (SPEC-ao-vivo.md):
  gerado_em_s?: number;
  atraso_s?: number;
  atualizacao_s?: number;
  janela_h?: number;
  intervalo_s?: number;
}

export interface Replay {
  meta: MetaDoReplay;
  modelo: ModeloDoReplay;
  fluxos: Fluxo[];
  medicoes: Medicao[];
}

/** As cores das classes e do desenho, lidas das variáveis CSS (as cores vivem só no CSS). */
export interface Cores {
  OK: string;
  RISCO: string;
  FALHA: string;
  tinta: string;
  papel: string;
  acao: string;
}
