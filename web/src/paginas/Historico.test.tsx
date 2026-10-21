// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Entrada, PaginaDePrevisoes } from "./api";
import { Historico, textoDaData } from "./Historico";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ENTRADA_VAZIA: Entrada = { z_robusto: null, aumento_pct: null, jitter_relativo: null, perda_pct: null, timeout_atual: null, n5_timeout: null, n5_aumento80: null, n5_moderado: null, min5_z: null, media5_z: null };

function pagina(total: number, itens: PaginaDePrevisoes["itens"], numero = 1): PaginaDePrevisoes {
  return { pagina: numero, tamanho: 25, total, itens };
}

function item(id: number, classe: "OK" | "RISCO" | "FALHA", extra: Partial<Entrada> = {}, origem = "api") {
  return {
    previsao: { id, criadaEmUtc: "2026-10-20T12:01:50.3601708Z", classe, probabilidades: { FALHA: 0.215, OK: 0.5, RISCO: 0.285 }, modeloSha256: "x" },
    entrada: { ...ENTRADA_VAZIA, ...extra },
    origem,
  };
}

function simular(corpo: unknown, status = 200) {
  const buscar = vi.fn().mockResolvedValue(new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", buscar);
  return buscar;
}

function renderizar(caminho = "/historico") {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <Historico />
    </MemoryRouter>,
  );
}

describe("textoDaData", () => {
  it("escreve a data em UTC, sem fração nem T", () => {
    expect(textoDaData("2026-10-20T12:01:50.3601708Z")).toBe("2026-10-20 12:01:50");
    expect(textoDaData("2026-10-20T12:01:50Z")).toBe("2026-10-20 12:01:50");
  });
});

describe("Histórico", () => {
  it("lista as previsões e usa um traço para o valor ausente", async () => {
    simular(pagina(2, [item(2, "FALHA", { z_robusto: 6, aumento_pct: 45.126, perda_pct: 0 }, "formulario"), item(1, "OK")]));
    renderizar();

    expect(await screen.findByText("2 previsões guardadas, da mais nova para a mais antiga.")).toBeInTheDocument();
    const linhas = screen.getAllByRole("row").slice(1); // sem o cabeçalho
    const primeira = within(linhas[0]).getAllByRole("cell").map((c) => c.textContent);
    expect(primeira).toEqual(["2026-10-20 12:01:50", "FALHA", "50.0%", "28.5%", "21.5%", "6", "45.13", "0", "formulario"]);
    const segunda = within(linhas[1]).getAllByRole("cell").map((c) => c.textContent);
    expect(segunda.slice(5, 8)).toEqual(["—", "—", "—"]); // z, aumento e perda ausentes
  });

  it("concorda o plural: 1 previsão guardada", async () => {
    simular(pagina(1, [item(1, "OK")]));
    renderizar();
    expect(await screen.findByText("1 previsão guardada, da mais nova para a mais antiga.")).toBeInTheDocument();
  });

  it("sem previsões, convida a fazer a primeira", async () => {
    simular(pagina(0, []));
    renderizar();
    expect(await screen.findByText(/Ainda não há previsões/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Testar o modelo" })).toHaveAttribute("href", "/testar");
  });

  it("pede a página da URL e liga os links de página", async () => {
    const buscar = simular(pagina(60, [item(30, "OK")], 2));
    renderizar("/historico?pagina=2");

    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
    expect(buscar.mock.calls[0][0]).toBe("/api/previsoes?pagina=2&tamanho=25");
    expect(screen.getByRole("link", { name: "← Mais novas" })).toHaveAttribute("href", "/historico?pagina=1");
    expect(screen.getByRole("link", { name: "Mais antigas →" })).toHaveAttribute("href", "/historico?pagina=3");
  });

  it("na primeira página não há link para as mais novas", async () => {
    simular(pagina(60, [item(60, "OK")]));
    renderizar();
    await screen.findByText("Página 1 de 3");
    expect(screen.queryByRole("link", { name: "← Mais novas" })).not.toBeInTheDocument();
  });

  it("mostra o erro da API em vez de uma tabela vazia", async () => {
    simular({ title: "O serviço do modelo está indisponível.", status: 503 }, 503);
    renderizar();
    expect(await screen.findByRole("alert")).toHaveTextContent("O serviço do modelo está indisponível.");
  });
});
