import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { lerReplay } from "../testes/replay";
import type { Replay } from "../tipos";
import { f1Macro } from "./placar";
import { avancarTempo, criarTempo, irParaTempo, regioesDosFluxos, terminou, ultimaConferidaDoFluxo, ultimaDoFluxo } from "./tempo";

const replay = lerReplay();

/** Uma cópia profunda e barata do replay para os testes que o estragam de propósito. */
function copia(): Replay {
  return structuredClone(replay);
}

describe("criarTempo (com o replay.json de verdade)", () => {
  it("começa um segundo antes da primeira medição, sem nada contado", () => {
    const tempo = criarTempo(replay);
    expect(tempo.agora).toBe(replay.medicoes[0].t - 1);
    expect(tempo.proxima).toBe(0);
    expect(tempo.placar.conferidas).toBe(0);
    expect(terminou(tempo)).toBe(false);
  });

  it("lê as 79 conexões, as 14.096 medições e as regiões em ordem alfabética", () => {
    expect(replay.fluxos).toHaveLength(79);
    expect(replay.medicoes).toHaveLength(14096);
    const regioes = regioesDosFluxos(replay.fluxos);
    expect(regioes).toEqual([...regioes].sort((a, b) => a.localeCompare(b, "pt-BR")));
    expect(new Set(regioes).size).toBe(regioes.length);
  });
});

// A prova de aceitação da etapa 2 (SPEC-go-react.md): ao fim do replay o placar da página é o da comparação dos modelos.
// Os números abaixo são os de `data/modelo/comparacao/matriz_comparacao.csv` (Random Forest e persistência, validação, N = 13.490),
// copiados para cá porque aquela pasta não vai para o git.
describe("o placar ao fim do replay é o da comparação (Random Forest, F1 macro 0,6977, N = 13.490)", () => {
  const tempo = criarTempo(replay);
  avancarTempo(tempo, tempo.fim);

  it("conferiu as 13.490 previsões e o relógio chegou ao fim", () => {
    expect(terminou(tempo)).toBe(true);
    expect(tempo.placar.conferidas).toBe(13_490);
  });

  it("a matriz de confusão da Random Forest é a publicada", () => {
    expect(tempo.placar.matriz).toEqual([
      [10082, 614, 75], // verdadeiro OK
      [940, 1154, 33], // verdadeiro RISCO
      [190, 103, 299], // verdadeiro FALHA
    ]);
  });

  it("o F1 macro é 0,6977", () => {
    expect(f1Macro(tempo.placar)).toBeCloseTo(0.6977, 4);
  });

  it("os acertos da floresta e do palpite simples (persistência) batem com as matrizes", () => {
    expect(tempo.placar.acertosArvore).toBe(10082 + 1154 + 299);
    expect(tempo.placar.acertosPersistencia).toBe(9634 + 1089 + 295);
  });

  it("confere com o CSV da comparação quando ele existe nesta máquina", () => {
    const arquivo = fileURLToPath(new URL("../../../data/modelo/comparacao/matriz_comparacao.csv", import.meta.url));
    let csv: string;
    try {
      csv = readFileSync(arquivo, "utf-8");
    } catch {
      return; // a pasta data/modelo/ não vai para o git: num clone limpo só valem as constantes acima
    }
    const linhas = csv.trim().split("\n").filter((linha) => linha.startsWith("random_forest,"));
    const esperada = linhas.map((linha) => linha.split(",").slice(2).map(Number));
    expect(tempo.placar.matriz).toEqual(esperada);
  });
});

describe("tocar até T e pular para T dão o mesmo estado", () => {
  const referencia = criarTempo(replay);
  const { inicio, fim } = referencia;
  const instantes = [0, 0.1, 0.33, 0.5, 0.77, 0.999, 1].map((fracao) => Math.round(inicio + fracao * (fim - inicio)));

  it.each(instantes)("no instante %d", (instante) => {
    // Tocando: quadros de 7 s da simulação (e um último que cai exatamente em `instante`).
    const tocando = criarTempo(replay);
    let soltas = 0;
    for (let t = tocando.inicio; t < instante; t += 7) {
      soltas += avancarTempo(tocando, Math.min(t + 7, instante)).soltas.length;
    }
    // Pulando: de uma vez, recalculando do zero.
    const pulando = criarTempo(replay);
    irParaTempo(pulando, instante);

    expect(tocando.agora).toBe(pulando.agora);
    expect(tocando.proxima).toBe(pulando.proxima);
    expect(soltas).toBe(pulando.proxima); // cada medição que aconteceu soltou exatamente um pulso
    expect(tocando.contagem).toEqual(pulando.contagem);
    expect(tocando.timeouts).toBe(pulando.timeouts);
    expect(tocando.semFuturo).toBe(pulando.semFuturo);
    expect(tocando.placar).toEqual(pulando.placar);
  });

  it("voltar no tempo recalcula do zero (pular para trás)", () => {
    const tempo = criarTempo(replay);
    avancarTempo(tempo, tempo.fim);
    irParaTempo(tempo, Math.round(inicio + 0.3 * (fim - inicio)));
    const direto = criarTempo(replay);
    irParaTempo(direto, tempo.agora);
    expect(tempo.placar).toEqual(direto.placar);
    expect(tempo.contagem).toEqual(direto.contagem);
  });

  it("o relógio nunca passa do fim nem fica antes do início", () => {
    const tempo = criarTempo(replay);
    irParaTempo(tempo, fim + 99_999);
    expect(tempo.agora).toBe(fim);
    irParaTempo(tempo, inicio - 99_999);
    expect(tempo.agora).toBe(inicio);
    expect(tempo.proxima).toBe(0);
  });
});

describe("a última medição de cada conexão", () => {
  const tempo = criarTempo(replay);
  irParaTempo(tempo, Math.round(tempo.inicio + 0.5 * (tempo.fim - tempo.inicio)));

  it("ultimaDoFluxo é a medição mais recente que já aconteceu", () => {
    const f = 5;
    const indice = ultimaDoFluxo(tempo, f);
    expect(indice).toBeGreaterThanOrEqual(0);
    expect(indice).toBeLessThan(tempo.proxima);
    expect(tempo.medicoes[indice].f).toBe(f);
    // Nenhuma medição do mesmo fluxo entre ela e o relógio.
    const depois = tempo.medicoes.slice(indice + 1, tempo.proxima).filter((m) => m.f === f);
    expect(depois).toHaveLength(0);
  });

  it("ultimaConferidaDoFluxo é a mais recente cuja previsão o relógio já conferiu", () => {
    const f = 5;
    const indice = ultimaConferidaDoFluxo(tempo, f);
    expect(indice).toBeGreaterThanOrEqual(0);
    const medicao = tempo.medicoes[indice];
    expect(medicao.conferivel).toBe(true);
    expect(medicao.t_futuro as number).toBeLessThanOrEqual(tempo.agora);
    const posteriores = tempo.medicoes.filter((m, i) => i > indice && m.f === f && i < tempo.proxima && m.conferivel && (m.t_futuro as number) <= tempo.agora);
    expect(posteriores).toHaveLength(0);
  });

  it("devolve -1 antes de o fluxo ter medido", () => {
    const comeco = criarTempo(replay);
    expect(ultimaDoFluxo(comeco, 0)).toBe(-1);
    expect(ultimaConferidaDoFluxo(comeco, 0)).toBe(-1);
  });
});

describe("validarReplay (via criarTempo)", () => {
  it("recusa um arquivo de versão antiga, sem t_futuro, com a dica de gerar de novo", () => {
    const antigo = copia();
    const conferivel = antigo.medicoes.find((m) => m.conferivel)!;
    conferivel.t_futuro = null;
    expect(() => criarTempo(antigo)).toThrow(/uv run python -m preditor_analise replay/);
  });

  it("recusa uma classe que a página não sabe colorir", () => {
    const estranho = copia();
    estranho.meta.classes = ["OK", "RISCO", "FALHA", "OUTRA"] as Replay["meta"]["classes"];
    expect(() => criarTempo(estranho)).toThrow(/exatamente/);
  });

  it("recusa medições fora da ordem de t", () => {
    const desordenado = copia();
    desordenado.medicoes[10].t = desordenado.medicoes[0].t - 100;
    expect(() => criarTempo(desordenado)).toThrow(/fora da ordem/);
  });

  it("recusa uma medição que aponta para um fluxo que não existe", () => {
    const quebrado = copia();
    quebrado.medicoes[0].f = 999;
    expect(() => criarTempo(quebrado)).toThrow(/não aponta para um fluxo/);
  });

  it("recusa a falta do bloco `modelo`", () => {
    const semModelo = copia() as Partial<Replay>;
    delete semModelo.modelo;
    expect(() => criarTempo(semModelo as Replay)).toThrow(/modelo/);
  });
});
