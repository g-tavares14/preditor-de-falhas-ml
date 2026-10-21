// motor.ts: o relógio do replay, o laço de animação e o estado da página do mapa (SPEC-visualizacao.md, SPEC-go-react.md).
//
// É o que `app.js` fazia com um objeto `estado` solto e escrevendo no DOM a cada quadro. Aqui a regra é outra: o motor mora FORA do
// React. O laço de `requestAnimationFrame` avança o relógio (logica/tempo.ts) e desenha no canvas (mapa/mapa.ts) sem passar pelo
// estado de nenhum componente. O React só LÊ um instantâneo imutável (`Instantaneo`) por `useSyncExternalStore`, e o motor só publica
// um novo quando algo que a tela mostra mudou ou, tocando, no máximo a cada INTERVALO_DO_INSTANTANEO_MS.
//
// Aqui não se calcula métrica nem rótulo: só se conta e se compara o que já vem no JSON.

import { SALTO_MAXIMO_S, instanteDoRelogio, mesmosFluxos } from "../logica/aovivo";
import { formatarPorcentagem, rotuloDoFluxo, textoDoInstante } from "../logica/comum";
import { acertou, ultimasConferencias } from "../logica/placar";
import { avancarTempo, criarTempo, irParaTempo, regioesDosFluxos, terminou, ultimaConferidaDoFluxo, ultimaDoFluxo, type Tempo } from "../logica/tempo";
import type { Mapa } from "../mapa/mapa";
import type { Classe, Fluxo, Medicao, ModeloDoReplay, Replay } from "../tipos";

// --- Constantes -----------------------------------------------------------------------------------------

/**
 * Velocidades oferecidas: quantos segundos DA SIMULAÇÃO passam a cada segundo real. A 300x as 12 h da validação duram cerca de 2 min
 * 24 s; a 60x, 12 min; a 900x, 48 s. Se subir o maior valor, rever `MAXIMO_DE_PULSOS` em mapa/pulsos.ts. Na tela aparecem com nome
 * (o número só na dica do botão e no aviso do leitor de tela).
 */
export const VELOCIDADES = [60, 300, 900] as const;
export const NOMES_DAS_VELOCIDADES: Record<number, string> = { 60: "Lento", 300: "Normal", 900: "Rápido" };
const VELOCIDADE_INICIAL = 300;

/**
 * Se a aba ficar escondida, o navegador pausa a animação; ao voltar, o primeiro quadro teria um salto enorme. Limitar o tempo de cada
 * quadro evita soltar milhares de pulsos de uma vez.
 */
const TEMPO_MAXIMO_DO_QUADRO_S = 0.1;

/**
 * A barra de tempo anda de 1 em 1 minuto (as setas do teclado) e o leitor de tela lê a hora dela de 2 em 2 segundos no máximo
 * enquanto o replay toca (decisão de acessibilidade: ler a cada quadro seria uma enxurrada de anúncios).
 */
export const PASSO_DA_BARRA_S = 60;
const INTERVALO_DO_TEXTO_DA_BARRA_S = 2;

/** Linhas do feed das últimas previsões conferidas (decisão visual: cabe no painel em 1280x720 junto com o resto). */
export const LINHAS_DO_FEED = 3;

/**
 * Com o replay tocando, o React recebe um instantâneo novo no máximo a cada tanto (10 por segundo). A 300x a hora da simulação anda
 * 300 s por segundo real; a cada 100 ms ela avança 30 s, que o olho lê como movimento contínuo. O canvas, esse sim, é desenhado a 60
 * quadros por segundo.
 */
const INTERVALO_DO_INSTANTANEO_MS = 100;

// --- O que o React enxerga ------------------------------------------------------------------------------

export interface ResumoDoPlacar {
  conferidas: number;
  acertosModelo: number;
  acertosPersistencia: number;
}

export interface ResumoDosContadores {
  porClasse: Record<Classe, number>;
  /** Medições exibidas até agora. */
  total: number;
  timeouts: number;
}

export interface DadosDoCartao {
  f: number;
  /** A última medição da conexão até o relógio, ou null se ainda não mediu. */
  medicao: Medicao | null;
  /** A última previsão da conexão que o relógio já conferiu, ou null. */
  conferida: Medicao | null;
}

export interface Instantaneo {
  inicio: number;
  fim: number;
  agora: number;
  tocando: boolean;
  terminou: boolean;
  velocidade: number;
  contadores: ResumoDosContadores;
  placar: ResumoDoPlacar;
  /** As últimas previsões conferidas (mais recente primeiro), já filtradas por região e por "só erros". */
  feed: Medicao[];
  regioesLigadas: ReadonlySet<string>;
  /** Alguma região está desligada? */
  filtroDeRegioes: boolean;
  soErros: boolean;
  selecionado: number | null;
  cartao: DadosDoCartao | null;
  /** O `aria-valuetext` da barra de tempo (data e hora): muda de 2 em 2 s no máximo enquanto toca. */
  textoDaBarra: string;
  /** A frase do aviso para o leitor de tela (aria-live); muda só quando o relógio para, recomeça ou acaba. */
  anuncio: string;
  /** Só ao vivo: quando o serviço gravou o arquivo que a página tem. */
  geradoEmS: number | null;
}

export interface OpcoesDoMotor {
  replay: Replay;
  aoVivo: boolean;
  /** Chamada com a mensagem de um erro do laço ou da atualização dos dados (a página a mostra). */
  aoErrar: (mensagem: string) => void;
}

type Ouvinte = () => void;

// --- O motor --------------------------------------------------------------------------------------------

export class Motor {
  readonly aoVivo: boolean;
  readonly fluxos: Fluxo[];
  readonly rotulos: string[];
  readonly todasAsRegioes: string[];
  readonly modelo: ModeloDoReplay;
  readonly totalDeMedicoes: number;
  /** Ao vivo: quanto o relógio fica atrás da hora real, e de quanto em quanto tempo o serviço consulta o Atlas. */
  readonly atrasoS: number;
  readonly intervaloDoServicoS: number;

  private tempo: Tempo;
  private mapa: Mapa | null = null;
  private readonly aoErrar: (mensagem: string) => void;
  private readonly ouvintes = new Set<Ouvinte>();

  private tocando = false;
  private velocidade: number;
  /** Segundos reais de animação (o relógio dos pulsos); ver `animacaoAnda`. */
  private relogioDaTela = 0;
  private regioesLigadas: Set<string>;
  private visivel: boolean[];
  private soErros = false;
  private selecionado: number | null = null;
  private situacaoAnunciada: "pausado" | "tocando" | "fim" = "pausado";
  private anuncio = "";
  private textoDaBarra = "";
  private quandoDoTextoDaBarra = -Infinity;
  private geradoEmS: number | null;

  private instantaneo: Instantaneo;
  private ultimaEmissaoMs = -Infinity;
  private pedidoDeQuadro: number | null = null;
  private ultimoQuadro: number | null = null;
  private ultimaFalha: string | null = null;

  constructor({ replay, aoVivo, aoErrar }: OpcoesDoMotor) {
    this.aoVivo = aoVivo;
    this.aoErrar = aoErrar;
    this.tempo = criarTempo(replay); // valida o JSON; lança erro com a dica de `replay` se for de versão antiga
    this.fluxos = replay.fluxos;
    this.rotulos = replay.fluxos.map(rotuloDoFluxo);
    this.todasAsRegioes = regioesDosFluxos(replay.fluxos);
    this.regioesLigadas = new Set(this.todasAsRegioes);
    this.visivel = replay.fluxos.map(() => true);
    this.modelo = replay.modelo;
    this.totalDeMedicoes = replay.medicoes.length;
    this.velocidade = aoVivo ? 1 : VELOCIDADE_INICIAL; // ao vivo o relógio anda em tempo real
    this.atrasoS = replay.meta.atraso_s ?? 0;
    this.geradoEmS = replay.meta.gerado_em_s ?? null;
    this.intervaloDoServicoS = replay.meta.intervalo_s ?? 60;
    this.instantaneo = this.montarInstantaneo(null);
  }

  // --- Leitura (useSyncExternalStore) -----------------------------------------------------------------

  readonly inscrever = (ouvinte: Ouvinte): (() => void) => {
    this.ouvintes.add(ouvinte);
    return () => this.ouvintes.delete(ouvinte);
  };

  readonly lerInstantaneo = (): Instantaneo => this.instantaneo;

  /** Os limites da barra de tempo: o `max` sobe até o próximo passo, para o placar final ser alcançável (ver `Relogio`). */
  get barra(): { min: number; max: number; passo: number } {
    const { inicio, fim } = this.tempo;
    return { min: inicio, max: inicio + Math.ceil((fim - inicio) / PASSO_DA_BARRA_S) * PASSO_DA_BARRA_S, passo: PASSO_DA_BARRA_S };
  }

  // --- Ligação com o mapa e o laço --------------------------------------------------------------------

  /** Liga o mapa recém-criado ao estado atual: selos com a última previsão de cada fluxo, filtro e seleção. */
  ligarMapa(mapa: Mapa): void {
    this.mapa = mapa;
    mapa.restaurar(this.ultimasMedicoes());
    mapa.definirVisiveis(this.visivel);
    mapa.definirSelecionado(this.selecionado);
    mapa.desenhar(this.relogioDaTela);
  }

  desligarMapa(): void {
    this.mapa = null;
  }

  /** Começa o laço de animação. Ao vivo, o relógio parte da hora real (menos o atraso) e toca sempre. */
  iniciar(): void {
    if (this.pedidoDeQuadro !== null) {
      return;
    }
    if (this.aoVivo && !this.tocando) {
      // Começa na hora real (menos o atraso): quem abre a página vê o estado de agora, não o começo do serviço.
      this.irParaInstante(instanteDoRelogio(Date.now(), this.atrasoS));
      this.tocando = true;
    }
    this.ultimoQuadro = null;
    this.pedidoDeQuadro = requestAnimationFrame(this.quadro);
    this.emitir();
  }

  parar(): void {
    if (this.pedidoDeQuadro !== null) {
      cancelAnimationFrame(this.pedidoDeQuadro);
      this.pedidoDeQuadro = null;
    }
  }

  // Um quadro: avança a animação e o relógio (conforme o estado) e desenha os pulsos. O próximo quadro é pedido ANTES do trabalho: se
  // algo abaixo lançar uma exceção, a animação não morre em silêncio.
  private readonly quadro = (agoraMs: number): void => {
    this.pedidoDeQuadro = requestAnimationFrame(this.quadro);
    const decorrido = this.ultimoQuadro === null ? 0 : (agoraMs - this.ultimoQuadro) / 1000;
    this.ultimoQuadro = agoraMs;
    const segundos = Math.max(0, Math.min(decorrido, TEMPO_MAXIMO_DO_QUADRO_S));
    try {
      if (this.animacaoAnda()) {
        this.relogioDaTela += segundos;
      }
      if (this.tocando) {
        this.avancarRelogio(segundos);
      }
      this.mapa?.desenhar(this.relogioDaTela);
      // Mudança de situação (pausou, acabou) é publicada na hora; o resto, no ritmo do INTERVALO_DO_INSTANTANEO_MS.
      // (Ao vivo o relógio nunca "para" nem "termina": a situação não é anunciada, então não há o que publicar por isso.)
      const situacaoMudou = !this.aoVivo && this.situacaoAtual() !== this.situacaoAnunciada;
      if (situacaoMudou || (this.tocando && agoraMs - this.ultimaEmissaoMs >= INTERVALO_DO_INSTANTANEO_MS)) {
        this.emitir(agoraMs);
      }
    } catch (erro) {
      const mensagem = erro instanceof Error ? erro.message : String(erro);
      if (mensagem !== this.ultimaFalha) {
        this.ultimaFalha = mensagem;
        console.error(erro);
        this.aoErrar(`Erro na animação: ${mensagem}`);
      }
    }
  };

  /**
   * O relógio da animação (dos pulsos) é separado do estado "tocando". Ele anda enquanto toca e também depois do fim do replay, para
   * os pulsos em voo terminarem; só o botão Pausar o congela (pausar congela os pulsos de propósito).
   */
  private animacaoAnda(): boolean {
    return this.tocando || terminou(this.tempo);
  }

  /**
   * Avança o relógio do replay e solta os pulsos das medições que "aconteceram" neste quadro (na ordem do JSON); as previsões que o
   * relógio acabou de conferir viram ✓ ou ✗ no selo do fluxo.
   */
  private avancarRelogio(segundosReais: number): void {
    const { tempo } = this;
    let instante = tempo.agora + segundosReais * this.velocidade;
    if (this.aoVivo) {
      // Ao vivo o relógio segue a hora real (menos o atraso). Se ficou muito para trás (aba escondida), pula em vez de soltar centenas
      // de pulsos de uma vez. O relógio nunca passa da última medição que a página tem (`tempo.fim`): o salto é medido até onde ele
      // PODE ir. Sem isto, com os dados parados há mais de SALTO_MAXIMO_S, `agora` voltaria a `fim` e o salto repetiria a cada quadro.
      const alvo = Math.min(instanteDoRelogio(Date.now(), this.atrasoS), tempo.fim);
      if (alvo - tempo.agora > SALTO_MAXIMO_S) {
        this.irParaInstante(alvo);
        return;
      }
      instante = alvo;
    }
    const { soltas, conferidas } = avancarTempo(tempo, instante);
    const mapa = this.mapa;
    if (mapa !== null) {
      for (const indice of soltas) {
        mapa.soltarPulso(tempo.medicoes[indice], this.relogioDaTela);
      }
      const duracao = mapa.duracaoDoVeredito(this.velocidade, tempo.intervaloTipicoS);
      for (const medicao of conferidas) {
        mapa.marcarConferencia(medicao.f, acertou(medicao), this.relogioDaTela, duracao);
      }
    }
    // No fim o relógio para na última medição, em vez de seguir adiante. Ao vivo não há fim: ele espera a próxima consulta.
    if (terminou(tempo) && !this.aoVivo) {
      this.tocando = false;
    }
  }

  // --- Ações ------------------------------------------------------------------------------------------

  /**
   * Pula o relógio para um instante qualquer (a barra de tempo e o botão Reiniciar). Tudo é recalculado do instante, sem soltar os
   * pulsos das medições puladas: o mapa recebe só a última previsão de cada fluxo (para os selos).
   */
  irParaInstante(instante: number): void {
    irParaTempo(this.tempo, instante);
    this.mapa?.restaurar(this.ultimasMedicoes());
    if (terminou(this.tempo) && !this.aoVivo) {
      this.tocando = false;
    }
    this.mapa?.desenhar(this.relogioDaTela);
    this.emitir();
  }

  /** Tocar / pausar; depois do fim, o mesmo botão recomeça do início. */
  alternarTocar(): void {
    if (terminou(this.tempo)) {
      this.irParaInstante(this.tempo.inicio);
      this.tocando = true;
    } else {
      this.tocando = !this.tocando;
    }
    this.emitir();
  }

  definirVelocidade(velocidade: number): void {
    this.velocidade = velocidade;
    this.emitir();
  }

  alternarRegiao(regiao: string, ligada: boolean): void {
    if (ligada) {
      this.regioesLigadas.add(regiao);
    } else {
      this.regioesLigadas.delete(regiao);
    }
    this.regioesLigadas = new Set(this.regioesLigadas); // outra referência: o React compara por identidade
    this.visivel = this.fluxos.map((fluxo) => this.regioesLigadas.has(fluxo.regiao));
    this.mapa?.definirVisiveis(this.visivel);
    // O cartão de um fluxo cuja região foi desligada fecha: a rota dele nem está mais no mapa.
    if (this.selecionado !== null && !this.visivel[this.selecionado]) {
      this.selecionar(null);
      return;
    }
    this.emitir();
  }

  definirSoErros(valor: boolean): void {
    this.soErros = valor;
    this.emitir();
  }

  /** Abre o cartão do fluxo `f` (ou fecha, com null) e destaca a rota dele no mapa. */
  selecionar(f: number | null): void {
    this.selecionado = f;
    this.mapa?.definirSelecionado(f);
    this.emitir();
  }

  /** Escreve no aviso para o leitor de tela (fora da tela): só quando algo importante muda, nunca a cada quadro. */
  anunciar(texto: string): void {
    this.anuncio = texto;
    this.emitir();
  }

  /** O elemento do selo do fluxo f (para devolver o foco a ele), ou null se a região dele está desligada. */
  alvoDoSelo(f: number): Element | null {
    return this.mapa?.alvoDoSelo(f) ?? null;
  }

  conferirCorte(): { rotas: number; pares: number; saltos: number } | null {
    return this.mapa?.conferirCorte() ?? null;
  }

  /**
   * Ao vivo: troca os dados SEM mexer no instante em que a página está: as medições que já passaram contam sem pulso, as seguintes
   * saem quando o relógio chegar nelas. Devolve false se a lista de conexões mudou (o serviço foi recomeçado): quem chamou recarrega.
   */
  substituirDados(novo: Replay): boolean {
    if (novo.meta.gerado_em_s === this.geradoEmS) {
      return true; // o serviço ainda não regravou
    }
    if (!mesmosFluxos(this.fluxos, novo.fluxos)) {
      return false;
    }
    const antes = this.tempo.agora;
    this.tempo = criarTempo(novo); // valida; se o arquivo estiver fora do formato, o erro aparece na página
    irParaTempo(this.tempo, antes);
    this.geradoEmS = novo.meta.gerado_em_s ?? null;
    this.emitir();
    return true;
  }

  // --- Instantâneo ------------------------------------------------------------------------------------

  /** A última medição de cada fluxo até o instante do relógio, ou null para o fluxo que ainda não mediu. */
  private ultimasMedicoes(): (Medicao | null)[] {
    const { tempo } = this;
    return this.fluxos.map((_, f) => {
      const indice = ultimaDoFluxo(tempo, f);
      return indice < 0 ? null : tempo.medicoes[indice];
    });
  }

  private situacaoAtual(): "pausado" | "tocando" | "fim" {
    return terminou(this.tempo) ? "fim" : this.tocando ? "tocando" : "pausado";
  }

  private emitir(agoraMs: number = performance.now()): void {
    this.ultimaEmissaoMs = agoraMs;
    this.anunciarMudancaDoRelogio();
    this.instantaneo = this.montarInstantaneo(this.instantaneo);
    this.ouvintes.forEach((ouvinte) => ouvinte());
  }

  /** Anuncia quando o replay passa a tocar, é pausado ou chega ao fim (e o placar nessas duas últimas). */
  private anunciarMudancaDoRelogio(): void {
    if (this.aoVivo) {
      return; // ao vivo o relógio nunca "para" nem "termina": nada a anunciar
    }
    const situacao = this.situacaoAtual();
    if (situacao === this.situacaoAnunciada) {
      return;
    }
    this.situacaoAnunciada = situacao;
    const hora = textoDoInstante(this.tempo.agora);
    const frases = {
      tocando: `Simulação tocando a ${this.velocidade} vezes a velocidade real.`,
      pausado: `Simulação pausada em ${hora}. ${this.frasePlacar()}`,
      fim: `Fim da simulação em ${hora}. ${this.frasePlacar()}`,
    };
    this.anuncio = frases[situacao];
  }

  /** O placar em uma frase: "Quanto o sistema acertou: 6733 de 8099 (83,1 %); palpite simples: 6567 de 8099 (81,1 %)." */
  private frasePlacar(): string {
    const { placar } = this.tempo;
    const pct = (acertos: number): string => `${acertos} de ${placar.conferidas} (${formatarPorcentagem(acertos, placar.conferidas)})`;
    return `Quanto o sistema acertou: ${pct(placar.acertosArvore)}; palpite simples (tudo igual a agora): ${pct(placar.acertosPersistencia)}.`;
  }

  /** Escreve o `aria-valuetext` da barra: parado vale na hora; tocando, só de 2 em 2 segundos reais. */
  private atualizarTextoDaBarra(): void {
    const texto = textoDoInstante(this.tempo.agora);
    const jaPassouTempo = this.relogioDaTela - this.quandoDoTextoDaBarra >= INTERVALO_DO_TEXTO_DA_BARRA_S;
    if (texto !== this.textoDaBarra && (!this.tocando || jaPassouTempo)) {
      this.textoDaBarra = texto;
      this.quandoDoTextoDaBarra = this.relogioDaTela;
    }
  }

  /**
   * Monta o instante a partir do estado, REAPROVEITANDO os objetos do anterior que não mudaram (contadores, placar, feed, cartão).
   * É isso que deixa os componentes com `memo` pularem a renderização: a referência é a mesma.
   */
  private montarInstantaneo(anterior: Instantaneo | null): Instantaneo {
    const { tempo } = this;
    this.atualizarTextoDaBarra();

    const contadores = reaproveitar(anterior?.contadores, {
      porClasse: { ...tempo.contagem } as Record<Classe, number>,
      total: tempo.proxima,
      timeouts: tempo.timeouts,
    });
    const placar = reaproveitar(anterior?.placar, {
      conferidas: tempo.placar.conferidas,
      acertosModelo: tempo.placar.acertosArvore,
      acertosPersistencia: tempo.placar.acertosPersistencia,
    });
    const feed = ultimasConferencias(tempo.placar, tempo.medicoes, tempo.conferencias, LINHAS_DO_FEED, (medicao) => this.visivel[medicao.f] && (!this.soErros || !acertou(medicao)));
    const f = this.selecionado;
    const cartao = f === null ? null : this.dadosDoCartao(f, anterior?.cartao ?? null);

    return {
      inicio: tempo.inicio,
      fim: tempo.fim,
      agora: tempo.agora,
      tocando: this.tocando,
      terminou: terminou(tempo),
      velocidade: this.velocidade,
      contadores,
      placar,
      feed: mesmosElementos(anterior?.feed, feed) ? (anterior?.feed as Medicao[]) : feed,
      regioesLigadas: this.regioesLigadas,
      filtroDeRegioes: this.regioesLigadas.size !== this.todasAsRegioes.length,
      soErros: this.soErros,
      selecionado: f,
      cartao,
      textoDaBarra: this.textoDaBarra,
      anuncio: this.anuncio,
      geradoEmS: this.geradoEmS,
    };
  }

  /** O cartão acompanha o relógio, mas só ganha objeto novo quando algo que ele mostra muda: outra conexão, uma medição nova dela ou uma previsão nova conferida. */
  private dadosDoCartao(f: number, anterior: DadosDoCartao | null): DadosDoCartao {
    const { tempo } = this;
    const indice = ultimaDoFluxo(tempo, f);
    const indiceConferida = ultimaConferidaDoFluxo(tempo, f);
    const medicao = indice < 0 ? null : tempo.medicoes[indice];
    const conferida = indiceConferida < 0 ? null : tempo.medicoes[indiceConferida];
    if (anterior !== null && anterior.f === f && anterior.medicao === medicao && anterior.conferida === conferida) {
      return anterior;
    }
    return { f, medicao, conferida };
  }
}

// --- Auxiliares -----------------------------------------------------------------------------------------

/** Devolve o objeto anterior se o novo tem exatamente os mesmos valores (comparação rasa; `porClasse` é comparado por dentro). */
function reaproveitar<T extends object>(anterior: T | undefined, novo: T): T {
  if (anterior === undefined) {
    return novo;
  }
  const iguais = (Object.keys(novo) as (keyof T)[]).every((chave) => {
    const a = anterior[chave];
    const b = novo[chave];
    return typeof b === "object" && b !== null ? JSON.stringify(a) === JSON.stringify(b) : a === b;
  });
  return iguais ? anterior : novo;
}

function mesmosElementos<T>(a: T[] | undefined, b: T[]): boolean {
  return a !== undefined && a.length === b.length && a.every((elemento, i) => elemento === b[i]);
}
