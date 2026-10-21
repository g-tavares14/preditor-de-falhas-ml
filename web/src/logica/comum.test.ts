import { describe, expect, it } from "vitest";
import type { Fluxo } from "../tipos";
import { formatarInstante, formatarPorcentagem, nomeDoPais, rotuloDoFluxo, textoDoInstante } from "./comum";

function fluxo(extra: Partial<Fluxo> = {}): Fluxo {
  return {
    id: "6349|129.143.66.65|23589837",
    regiao: "Europa",
    pais: "DE",
    opcao: "",
    km: 1,
    rtt_minimo_ms: 1,
    mediana_ms: 1,
    trechos: [{ tipo: "terrestre", nome: "x", km: 1, caminho: [], nos: [{ tipo: "destino", nome: "Frankfurt (129.143.66.65)", ponto: [8, 50] }] }],
    ...extra,
  };
}

describe("formatarInstante", () => {
  it("escreve dia/mês/ano e a hora, sempre em UTC", () => {
    expect(formatarInstante(1790194198)).toEqual({ data: "23/09/2026", hora: "20:09:58" });
    expect(textoDoInstante(1790194198)).toBe("23/09/2026 20:09:58 UTC");
  });
});

describe("formatarPorcentagem", () => {
  it("usa uma casa e vírgula, e um traço quando nada foi conferido", () => {
    expect(formatarPorcentagem(6733, 8099)).toBe("83,1 %");
    expect(formatarPorcentagem(0, 0)).toBe("--");
  });
});

describe("rotuloDoFluxo", () => {
  it("no replay a sonda é do Brasil e o rótulo não cita o país", () => {
    expect(rotuloDoFluxo(fluxo())).toBe("Ponto 6349 → Frankfurt");
  });

  it("no ao vivo cita o país do ponto de medição", () => {
    expect(rotuloDoFluxo(fluxo({ origem_pais: "CL" }))).toBe("Ponto 6349 (Chile) → Frankfurt");
  });
});

describe("nomeDoPais", () => {
  it("devolve o código quando não conhece o país", () => {
    expect(nomeDoPais("BR")).toBe("Brasil");
    expect(nomeDoPais("ZZ")).toBe("ZZ");
  });
});
