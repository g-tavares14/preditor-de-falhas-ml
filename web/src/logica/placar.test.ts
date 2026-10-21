import { describe, expect, it } from "vitest";
import type { Classe, Medicao } from "../tipos";
import { acertou, conferirAte, criarPlacar, f1Macro, listarConferencias, placarAte, ultimasConferencias } from "./placar";

const CLASSES: Classe[] = ["OK", "RISCO", "FALHA"];

function medicao(extra: Partial<Medicao>): Medicao {
  return { f: 0, t: 0, rtt: 100, timeout: 0, atual: "OK", previsto: "OK", futuro: "OK", conferivel: true, t_futuro: 10, ...extra };
}

describe("listarConferencias", () => {
  it("só inclui as conferíveis, em ordem de t_futuro, e mantém a ordem do JSON no empate", () => {
    const medicoes = [
      medicao({ t_futuro: 30 }),
      medicao({ conferivel: false, futuro: null, t_futuro: null }),
      medicao({ t_futuro: 10 }),
      medicao({ t_futuro: 10 }),
    ];
    expect(listarConferencias(medicoes)).toEqual([
      { indice: 2, tFuturo: 10 },
      { indice: 3, tFuturo: 10 },
      { indice: 0, tFuturo: 30 },
    ]);
  });

  it("falha alto com uma medição conferível sem t_futuro (arquivo de versão antiga)", () => {
    expect(() => listarConferencias([medicao({ t_futuro: null })])).toThrow(/t_futuro/);
  });
});

describe("placar", () => {
  const medicoes = [
    medicao({ atual: "OK", previsto: "OK", futuro: "OK", t_futuro: 10 }), // modelo certo, persistência certa
    medicao({ atual: "OK", previsto: "FALHA", futuro: "FALHA", t_futuro: 20 }), // modelo certo, persistência errada
    medicao({ atual: "RISCO", previsto: "OK", futuro: "RISCO", t_futuro: 30 }), // modelo errado, persistência certa
  ];
  const conferencias = listarConferencias(medicoes);

  it("só conta o que o relógio já alcançou (t_futuro <= instante)", () => {
    const placar = criarPlacar(CLASSES);
    expect(conferirAte(placar, medicoes, conferencias, 9)).toHaveLength(0);
    expect(conferirAte(placar, medicoes, conferencias, 20)).toHaveLength(2);
    expect(placar.conferidas).toBe(2);
    expect(placar.acertosArvore).toBe(2);
    expect(placar.acertosPersistencia).toBe(1);
  });

  it("pular para o instante dá o mesmo placar que tocar até ele", () => {
    const tocando = criarPlacar(CLASSES);
    for (const instante of [5, 12, 25, 31]) {
      conferirAte(tocando, medicoes, conferencias, instante);
    }
    expect(placarAte(CLASSES, medicoes, conferencias, 31)).toEqual(tocando);
  });

  it("monta a matriz com a linha = verdadeiro e a coluna = previsto", () => {
    const placar = placarAte(CLASSES, medicoes, conferencias, 100);
    expect(placar.matriz).toEqual([
      [1, 0, 0], // verdadeiro OK: previsto OK
      [1, 0, 0], // verdadeiro RISCO: o modelo previu OK
      [0, 0, 1], // verdadeiro FALHA: previsto FALHA
    ]);
  });

  it("uma classe fora de `classes` é erro, não uma contagem torta", () => {
    const quebrada = [medicao({ previsto: "DESCONHECIDA" as Classe })];
    expect(() => placarAte(CLASSES, quebrada, listarConferencias(quebrada), 100)).toThrow(/classe desconhecida/);
  });

  it("acertou compara previsto com futuro", () => {
    expect(acertou(medicao({ previsto: "OK", futuro: "OK" }))).toBe(true);
    expect(acertou(medicao({ previsto: "OK", futuro: "RISCO" }))).toBe(false);
  });
});

describe("ultimasConferencias", () => {
  const medicoes = [1, 2, 3, 4, 5].map((n) => medicao({ f: n % 2, t: n, t_futuro: n * 10, previsto: n % 2 ? "OK" : "FALHA", futuro: "OK" }));
  const conferencias = listarConferencias(medicoes);
  const placar = placarAte(CLASSES, medicoes, conferencias, 1000);

  it("devolve as mais recentes primeiro", () => {
    expect(ultimasConferencias(placar, medicoes, conferencias, 2).map((m) => m.t)).toEqual([5, 4]);
  });

  it("aplica o filtro sem mexer no placar, e para ao juntar `quantas`", () => {
    const soErros = ultimasConferencias(placar, medicoes, conferencias, 5, (m) => !acertou(m));
    expect(soErros.map((m) => m.t)).toEqual([4, 2]);
    expect(placar.conferidas).toBe(5);
  });
});

describe("f1Macro", () => {
  it("é a média dos F1 de cada classe, lidos da matriz", () => {
    const placar = criarPlacar(CLASSES);
    placar.matriz = [
      [8, 2, 0],
      [1, 4, 0],
      [0, 0, 0], // nenhuma FALHA de verdade nem prevista: F1 = 0, sem dividir por zero
    ];
    const f1Ok = (2 * (8 / 9) * (8 / 10)) / (8 / 9 + 8 / 10);
    const f1Risco = (2 * (4 / 6) * (4 / 5)) / (4 / 6 + 4 / 5);
    expect(f1Macro(placar)).toBeCloseTo((f1Ok + f1Risco + 0) / 3, 10);
  });
});
