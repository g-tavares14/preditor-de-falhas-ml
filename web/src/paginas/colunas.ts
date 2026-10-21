// colunas.ts: os nomes e as explicações das 10 colunas, para a tela Testar (o texto de ajuda vem de `docs/` e da RFC §8), e os casos
// prontos para a apresentação (os mesmos valores do `exemplo_de_uso.py` do modelo exportado).

import type { Entrada, NomeDaColuna } from "./api";

export interface ColunaDoModelo {
  nome: NomeDaColuna;
  titulo: string;
  ajuda: string;
  /** O `step` do <input type=number>: "any" aceita decimais; "1" só inteiros. */
  passo: "any" | "1";
}

export const COLUNAS: ColunaDoModelo[] = [
  { nome: "z_robusto", titulo: "z robusto", ajuda: "Quantos desvios (robustos) o RTT de agora está acima do normal da rota.", passo: "any" },
  { nome: "aumento_pct", titulo: "Aumento do RTT (%)", ajuda: "Quanto o RTT de agora passa da mediana do baseline da rota.", passo: "any" },
  { nome: "jitter_relativo", titulo: "Jitter relativo", ajuda: "Jitter de agora dividido pelo jitter típico da rota.", passo: "any" },
  { nome: "perda_pct", titulo: "Perda (%)", ajuda: "Pings sem resposta na rajada, de 0 a 100.", passo: "any" },
  { nome: "timeout_atual", titulo: "Timeout agora", ajuda: "1 se a medição de agora deu timeout, senão 0.", passo: "1" },
  { nome: "n5_timeout", titulo: "Timeouts nas últimas 5", ajuda: "De 0 a 5.", passo: "1" },
  { nome: "n5_aumento80", titulo: "Aumentos ≥ 80% nas últimas 5", ajuda: "De 0 a 5.", passo: "1" },
  { nome: "n5_moderado", titulo: "Aumentos moderados nas últimas 5", ajuda: "De 0 a 5.", passo: "1" },
  { nome: "min5_z", titulo: "Menor z nas últimas 5", ajuda: "O menor z robusto da janela.", passo: "any" },
  { nome: "media5_z", titulo: "Média do z nas últimas 5", ajuda: "A média do z robusto da janela.", passo: "any" },
];

export interface Exemplo {
  titulo: string;
  entrada: Entrada;
}

export const EXEMPLOS: Record<string, Exemplo> = {
  estavel: {
    titulo: "Rota estável",
    entrada: { z_robusto: 0.3, aumento_pct: 2.0, jitter_relativo: 1.1, perda_pct: 0.0, timeout_atual: 0, n5_timeout: 0, n5_aumento80: 0, n5_moderado: 0, min5_z: -0.5, media5_z: -0.1 },
  },
  pico: {
    titulo: "Pico de agora",
    entrada: { z_robusto: 6.0, aumento_pct: 45.0, jitter_relativo: 2.0, perda_pct: 0.0, timeout_atual: 0, n5_timeout: 0, n5_aumento80: 0, n5_moderado: 1, min5_z: 0.1, media5_z: 0.5 },
  },
  timeout: {
    titulo: "Sem RTT nesta medição",
    entrada: { z_robusto: null, aumento_pct: null, jitter_relativo: null, perda_pct: 100.0, timeout_atual: 1, n5_timeout: 2, n5_aumento80: 0, n5_moderado: 2, min5_z: null, media5_z: null },
  },
};
