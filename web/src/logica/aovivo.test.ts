import { describe, expect, it } from "vitest";
import type { Fluxo } from "../tipos";
import { instanteDoRelogio, mesmosFluxos, modoAoVivo, servicoParado, textoDaIdade } from "./aovivo";

const fluxo = (id: string) => ({ id }) as Fluxo;

describe("modoAoVivo", () => {
  it("liga com ?ao-vivo, com ou sem valor", () => {
    expect(modoAoVivo("?ao-vivo")).toBe(true);
    expect(modoAoVivo("?ao-vivo=1")).toBe(true);
    expect(modoAoVivo("?outro=1&ao-vivo")).toBe(true);
  });

  it("fica no replay sem o parâmetro", () => {
    expect(modoAoVivo("")).toBe(false);
    expect(modoAoVivo("?aovivo")).toBe(false);
  });
});

describe("instanteDoRelogio", () => {
  it("é a hora real em segundos menos o atraso", () => {
    expect(instanteDoRelogio(1_790_000_000_999, 300)).toBe(1_789_999_700);
  });
});

describe("mesmosFluxos", () => {
  it("exige os mesmos ids na mesma ordem", () => {
    expect(mesmosFluxos([fluxo("a"), fluxo("b")], [fluxo("a"), fluxo("b")])).toBe(true);
    expect(mesmosFluxos([fluxo("a"), fluxo("b")], [fluxo("b"), fluxo("a")])).toBe(false);
    expect(mesmosFluxos([fluxo("a")], [fluxo("a"), fluxo("b")])).toBe(false);
  });
});

describe("textoDaIdade", () => {
  it.each([
    [0, "agora mesmo"],
    [9.9, "agora mesmo"],
    [10, "há 10 s"],
    [40, "há 40 s"],
    [89, "há 89 s"],
    [90, "há 2 min"],
    [180, "há 3 min"],
    [5399, "há 90 min"],
    [5400, "há 2 h"],
    [7200, "há 2 h"],
  ])("%d s → %s", (segundos, texto) => {
    expect(textoDaIdade(segundos)).toBe(texto);
  });
});

describe("servicoParado", () => {
  it("avisa depois de 3 consultas sem regravar o arquivo", () => {
    expect(servicoParado(180, 60)).toBe(false);
    expect(servicoParado(181, 60)).toBe(true);
  });
});
