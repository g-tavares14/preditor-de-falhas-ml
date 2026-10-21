import { beforeEach, describe, expect, it, vi } from "vitest";
import { lerReplay } from "../testes/replay";
import type { Replay } from "../tipos";
import type { Mapa } from "../mapa/mapa";
import { Motor } from "./motor";

const replay = lerReplay();

/** Um mapa de mentira: o motor só chama estes métodos, e os testes conferem as chamadas. */
function mapaFalso(): Mapa {
  return {
    soltarPulso: vi.fn(),
    marcarConferencia: vi.fn(),
    duracaoDoVeredito: () => 0.25,
    desenhar: vi.fn(),
    restaurar: vi.fn(),
    definirVisiveis: vi.fn(),
    definirSelecionado: vi.fn(),
    alvoDoSelo: () => null,
    conferirCorte: () => ({ rotas: 79, pares: 1, saltos: 0 }),
    destruir: vi.fn(),
  };
}

function criar(opcoes: { aoVivo?: boolean; replay?: Replay } = {}) {
  const aoErrar = vi.fn();
  const motor = new Motor({ replay: opcoes.replay ?? replay, aoVivo: opcoes.aoVivo ?? false, aoErrar });
  const mapa = mapaFalso();
  motor.ligarMapa(mapa);
  return { motor, mapa, aoErrar };
}

describe("instantâneo", () => {
  let motor: Motor;
  beforeEach(() => ({ motor } = criar()));

  it("começa parado, no início, na velocidade Normal, sem nada contado", () => {
    const inst = motor.lerInstantaneo();
    expect(inst.tocando).toBe(false);
    expect(inst.terminou).toBe(false);
    expect(inst.velocidade).toBe(300);
    expect(inst.contadores.total).toBe(0);
    expect(inst.placar.conferidas).toBe(0);
    expect(inst.feed).toEqual([]);
    expect(inst.selecionado).toBeNull();
    expect(inst.regioesLigadas.size).toBe(motor.todasAsRegioes.length);
  });

  it("devolve a MESMA referência enquanto nada muda (exigência do useSyncExternalStore)", () => {
    expect(motor.lerInstantaneo()).toBe(motor.lerInstantaneo());
  });

  it("não avisa os ouvintes por conta própria, só quando alguém age", () => {
    const ouvinte = vi.fn();
    motor.inscrever(ouvinte);
    motor.lerInstantaneo();
    expect(ouvinte).not.toHaveBeenCalled();
    motor.definirVelocidade(900);
    expect(ouvinte).toHaveBeenCalledTimes(1);
  });

  it("pular no tempo muda o instantâneo e restaura os selos do mapa, sem soltar pulsos", () => {
    const { motor, mapa } = criar();
    const { inicio, fim } = motor.lerInstantaneo();
    const meio = Math.round(inicio + (fim - inicio) / 2);

    motor.irParaInstante(meio);

    const inst = motor.lerInstantaneo();
    expect(inst.agora).toBe(meio);
    expect(inst.contadores.total).toBeGreaterThan(0);
    expect(inst.placar.conferidas).toBeGreaterThan(0);
    expect(mapa.restaurar).toHaveBeenCalled();
    expect(mapa.soltarPulso).not.toHaveBeenCalled();
  });

  it("pular para o fim para o relógio e o botão passa a recomeçar", () => {
    const { motor } = criar();
    motor.alternarTocar();
    expect(motor.lerInstantaneo().tocando).toBe(true);

    motor.irParaInstante(motor.lerInstantaneo().fim);

    const inst = motor.lerInstantaneo();
    expect(inst.terminou).toBe(true);
    expect(inst.tocando).toBe(false);
    expect(inst.placar.conferidas).toBe(13_490); // o placar final da comparação
    expect(inst.anuncio).toMatch(/^Fim da simulação em 24\/09\/2026 08:08:05 UTC\. Quanto o sistema acertou: 11535 de 13490/);

    motor.alternarTocar(); // depois do fim, o mesmo botão recomeça do início
    expect(motor.lerInstantaneo().tocando).toBe(true);
    expect(motor.lerInstantaneo().terminou).toBe(false);
    expect(motor.lerInstantaneo().placar.conferidas).toBe(0);
  });

  it("reaproveita o objeto do placar quando só o relógio mudou", () => {
    const { motor } = criar();
    const antes = motor.lerInstantaneo();
    motor.definirVelocidade(60); // nada do placar, dos contadores ou do feed muda
    const depois = motor.lerInstantaneo();
    expect(depois).not.toBe(antes);
    expect(depois.placar).toBe(antes.placar);
    expect(depois.contadores).toBe(antes.contadores);
    expect(depois.feed).toBe(antes.feed);
  });
});

describe("anúncio para o leitor de tela", () => {
  it("diz que está tocando e depois que pausou, com o placar", () => {
    const { motor } = criar();
    motor.alternarTocar();
    expect(motor.lerInstantaneo().anuncio).toBe("Simulação tocando a 300 vezes a velocidade real.");
    motor.alternarTocar();
    expect(motor.lerInstantaneo().anuncio).toMatch(/^Simulação pausada em \d\d\/09\/2026 \d\d:\d\d:\d\d UTC\. Quanto o sistema acertou: /);
  });

  it("não anuncia nada ao vivo (o relógio nunca para nem termina)", () => {
    const { motor } = criar({ aoVivo: true });
    motor.alternarTocar();
    expect(motor.lerInstantaneo().anuncio).toBe("");
  });

  it("o texto da barra de tempo é a data e a hora UTC", () => {
    const { motor } = criar();
    motor.irParaInstante(motor.lerInstantaneo().inicio + 3600);
    expect(motor.lerInstantaneo().textoDaBarra).toMatch(/^\d\d\/09\/2026 \d\d:\d\d:\d\d UTC$/);
  });
});

describe("filtro por região e seleção", () => {
  it("desligar uma região esconde os fluxos dela no mapa e tira as previsões dela do feed", () => {
    const { motor, mapa } = criar();
    motor.irParaInstante(motor.lerInstantaneo().fim);
    const regiao = motor.fluxos[motor.lerInstantaneo().feed[0].f].regiao;

    motor.alternarRegiao(regiao, false);

    const inst = motor.lerInstantaneo();
    expect(inst.filtroDeRegioes).toBe(true);
    expect(inst.regioesLigadas.has(regiao)).toBe(false);
    expect(inst.feed.every((m) => motor.fluxos[m.f].regiao !== regiao)).toBe(true);
    const visiveis = (mapa.definirVisiveis as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[0] as boolean[];
    expect(visiveis.filter(Boolean).length).toBeLessThan(motor.fluxos.length);
    expect(inst.placar.conferidas).toBe(13_490); // o placar não é filtrado

    motor.alternarRegiao(regiao, true);
    expect(motor.lerInstantaneo().filtroDeRegioes).toBe(false);
  });

  it("'só os erros' deixa no feed só as previsões erradas", () => {
    const { motor } = criar();
    motor.irParaInstante(motor.lerInstantaneo().fim);
    motor.definirSoErros(true);
    const feed = motor.lerInstantaneo().feed;
    expect(feed.length).toBeGreaterThan(0);
    expect(feed.every((m) => m.previsto !== m.futuro)).toBe(true);
  });

  it("selecionar abre o cartão da conexão e destaca a rota; fechar limpa", () => {
    const { motor, mapa } = criar();
    motor.irParaInstante(motor.lerInstantaneo().fim);

    motor.selecionar(5);
    const cartao = motor.lerInstantaneo().cartao;
    expect(cartao?.f).toBe(5);
    expect(cartao?.medicao?.f).toBe(5);
    expect(cartao?.conferida?.conferivel).toBe(true);
    expect(mapa.definirSelecionado).toHaveBeenLastCalledWith(5);

    motor.selecionar(null);
    expect(motor.lerInstantaneo().cartao).toBeNull();
    expect(mapa.definirSelecionado).toHaveBeenLastCalledWith(null);
  });

  it("desligar a região da conexão aberta fecha o cartão", () => {
    const { motor } = criar();
    motor.selecionar(5);
    motor.alternarRegiao(motor.fluxos[5].regiao, false);
    expect(motor.lerInstantaneo().selecionado).toBeNull();
  });

  it("ligar um mapa novo (StrictMode monta duas vezes) o reata ao estado atual", () => {
    const { motor } = criar();
    motor.irParaInstante(motor.lerInstantaneo().inicio + 7200);
    motor.alternarRegiao(motor.fluxos[0].regiao, false);
    motor.selecionar(7);

    const novo = mapaFalso();
    motor.ligarMapa(novo);

    expect(novo.restaurar).toHaveBeenCalled();
    expect(novo.definirVisiveis).toHaveBeenCalled();
    expect(novo.definirSelecionado).toHaveBeenCalledWith(7);
  });
});

describe("ao vivo: substituirDados", () => {
  function aoVivo(geradoEm: number): Replay {
    const copia = structuredClone(replay);
    copia.meta = { ...copia.meta, gerado_em_s: geradoEm, atraso_s: 300, atualizacao_s: 30, intervalo_s: 60 };
    return copia;
  }

  it("ignora o arquivo que o serviço ainda não regravou", () => {
    const { motor } = criar({ aoVivo: true, replay: aoVivo(1000) });
    const antes = motor.lerInstantaneo();
    expect(motor.substituirDados(aoVivo(1000))).toBe(true);
    expect(motor.lerInstantaneo()).toBe(antes);
  });

  it("troca os dados sem mexer no instante em que a página está", () => {
    const { motor } = criar({ aoVivo: true, replay: aoVivo(1000) });
    const meio = motor.lerInstantaneo().inicio + 5000;
    motor.irParaInstante(meio);

    expect(motor.substituirDados(aoVivo(1060))).toBe(true);

    const inst = motor.lerInstantaneo();
    expect(inst.agora).toBe(meio);
    expect(inst.geradoEmS).toBe(1060);
  });

  it("recusa (e a página recarrega) se a lista de conexões mudou", () => {
    const { motor } = criar({ aoVivo: true, replay: aoVivo(1000) });
    const outro = aoVivo(1060);
    outro.fluxos = outro.fluxos.slice().reverse();
    expect(motor.substituirDados(outro)).toBe(false);
  });
});
