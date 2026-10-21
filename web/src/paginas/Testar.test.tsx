// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Testar } from "./Testar";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const RESPOSTA_OK = {
  id: 1,
  criadaEmUtc: "2026-10-20T12:00:00Z",
  classe: "RISCO",
  probabilidades: { FALHA: 0.1, OK: 0.2, RISCO: 0.7 },
  modeloSha256: "abc123",
};

function resposta(status: number, corpo: unknown): Response {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": status === 200 ? "application/json" : "application/problem+json" } });
}

function renderizar(caminho = "/testar") {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <Testar />
    </MemoryRouter>,
  );
}

const campo = (nome: string) => document.querySelector<HTMLInputElement>(`input[name=${nome}]`) as HTMLInputElement;

describe("Testar o modelo", () => {
  it("começa com todos os campos vazios (ausente), sem resultado", () => {
    renderizar();
    expect(document.querySelectorAll("input[type=number]")).toHaveLength(10);
    expect([...document.querySelectorAll<HTMLInputElement>("input[type=number]")].every((i) => i.value === "")).toBe(true);
    expect(screen.queryByText(/Previsão para daqui a 12 minutos/)).not.toBeInTheDocument();
  });

  it("um exemplo da URL preenche o formulário", () => {
    renderizar("/testar?exemplo=pico");
    expect(campo("z_robusto").value).toBe("6");
    expect(campo("aumento_pct").value).toBe("45");
    expect(campo("n5_moderado").value).toBe("1");
  });

  it("o exemplo sem RTT deixa vazios os campos ausentes", () => {
    renderizar("/testar?exemplo=timeout");
    expect(campo("z_robusto").value).toBe("");
    expect(campo("perda_pct").value).toBe("100");
    expect(campo("timeout_atual").value).toBe("1");
  });

  it("envia JSON com null nos campos vazios (nunca zero) e origem=formulario, e mostra a previsão", async () => {
    const buscar = vi.fn().mockResolvedValue(resposta(200, RESPOSTA_OK));
    vi.stubGlobal("fetch", buscar);
    renderizar();
    const usuario = userEvent.setup();

    await usuario.type(campo("z_robusto"), "6.5");
    await usuario.type(campo("perda_pct"), "0");
    await usuario.click(screen.getByRole("button", { name: "Prever" }));

    await waitFor(() => expect(screen.getByText("RISCO", { selector: ".classe" })).toBeInTheDocument());
    const [url, init] = buscar.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/previsoes?origem=formulario");
    expect(init.method).toBe("POST");
    const corpo = JSON.parse(init.body as string) as Record<string, number | null>;
    expect(Object.keys(corpo)).toHaveLength(10); // as 10 colunas sempre vão
    expect(corpo.z_robusto).toBe(6.5);
    expect(corpo.perda_pct).toBe(0); // zero digitado é zero...
    expect(corpo.aumento_pct).toBeNull(); // ...e campo vazio é ausente, não zero
    expect(screen.getByText("70.0%")).toBeInTheDocument();
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it("mostra o erro de cada coluna ao lado do campo, sem mostrar previsão", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(resposta(400, { title: "Há colunas com valor inválido.", status: 400, errors: { perda_pct: ["Tem de estar entre 0 e 100."], n5_timeout: ["Tem de ser um inteiro de 0 a 5."] } })),
    );
    renderizar();
    const usuario = userEvent.setup();

    await usuario.type(campo("perda_pct"), "150");
    await usuario.click(screen.getByRole("button", { name: "Prever" }));

    expect(await screen.findByText("Tem de estar entre 0 e 100.")).toBeInTheDocument();
    expect(campo("perda_pct").parentElement).toHaveTextContent("Tem de estar entre 0 e 100.");
    expect(campo("n5_timeout").parentElement).toHaveTextContent("Tem de ser um inteiro de 0 a 5.");
    expect(screen.queryByText(/Previsão para daqui a 12 minutos/)).not.toBeInTheDocument();
  });

  it("explica o serviço do modelo fora do ar e diz que nada foi gravado", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(resposta(503, { title: "O serviço do modelo está indisponível.", status: 503, detail: "Não consegui falar com o serviço do modelo." })));
    renderizar();

    await userEvent.setup().click(screen.getByRole("button", { name: "Prever" }));

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("O serviço do modelo não respondeu: Não consegui falar com o serviço do modelo.");
    expect(aviso).toHaveTextContent("Nada foi gravado.");
    expect(screen.queryByText(/Previsão para daqui a 12 minutos/)).not.toBeInTheDocument();
  });

  it("sem rede, avisa em vez de ficar parado", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderizar();

    await userEvent.setup().click(screen.getByRole("button", { name: "Prever" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Não consegui falar com o servidor.");
    expect(screen.getByRole("button", { name: "Prever" })).toBeEnabled();
  });
});
