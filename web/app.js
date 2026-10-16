// app.js: relógio do replay, controles e teclado (SPEC-visualizacao.md).
//
// Lê `dados/replay.json` (gerado por `uv run python -m preditor replay`) e reproduz as medições em tempo acelerado. Com `?ao-vivo`
// na página lê `dados/aovivo.json` (gerado pelo serviço `uv run python -m preditor aovivo`, SPEC-ao-vivo.md): o mesmo formato, mas o
// relógio anda em tempo real (atrasado) e o arquivo é relido de tempos em tempos; ver aovivo.js.
// Quem faz o quê: mapa.js (e rotas.js, desenho.js, pulsos.js, selos.js, foco.js) desenha o mapa e os pulsos; tempo.js e
// placar.js fazem as contas do relógio e do placar (sem DOM, rodam em Node); painel.js monta o placar e o feed;
// cartao.js, o cartão da conexão. Aqui não se calcula métrica nem rótulo: só se conta e se compara o que já vem no JSON.
// A página é para quem não é da área (sem árvore, matriz nem termos técnicos): os nomes na tela vêm de comum.js.

import { ARQUIVO_AO_VIVO, MENSAGEM_SEM_DADOS_AO_VIVO, SALTO_MAXIMO_S, instanteDoRelogio, mesmosFluxos, modoAoVivo, servicoParado, textoDaIdade } from "./aovivo.js";
import { atualizarCartao } from "./cartao.js";
import { criarCelula, formatarInstante, rotuloDoFluxo } from "./comum.js";
import { criarMapa } from "./mapa.js";
import { ROTACAO_AO_VIVO } from "./rotas.js";
import { atualizarPlacarSeMudou, formatarPorcentagem, montarFeed } from "./painel.js";
import { acertou } from "./placar.js";
import { DICA_REPLAY, avancarTempo, criarTempo, irParaTempo, regioesDosFluxos, terminou, ultimaDoFluxo } from "./tempo.js";

// --- Constantes -----------------------------------------------------------------------------------------

// Velocidades oferecidas: quantos segundos DA SIMULAÇÃO passam a cada segundo real. A 300x as 12 h da validação duram
// cerca de 2 min 24 s; a 60x, 12 min; a 900x, 48 s. Se subir o maior valor, rever `MAXIMO_DE_PULSOS` em mapa.js.
// Na tela aparecem com nome (o número só na dica do botão e no aviso do leitor de tela).
const VELOCIDADES = [60, 300, 900];
const NOMES_DAS_VELOCIDADES = { 60: "Lento", 300: "Normal", 900: "Rápido" };
const VELOCIDADE_INICIAL = 300;

// Se a aba ficar escondida, o navegador pausa a animação; ao voltar, o primeiro quadro teria um salto enorme.
// Limitar o tempo de cada quadro evita soltar milhares de pulsos de uma vez.
const TEMPO_MAXIMO_DO_QUADRO_S = 0.1;

// A barra de tempo anda de 1 em 1 minuto (as setas do teclado) e o leitor de tela lê a hora dela de 2 em 2 segundos no
// máximo enquanto o replay toca (decisão de acessibilidade: ler a cada quadro seria uma enxurrada de anúncios).
const PASSO_DA_BARRA_S = 60;
const INTERVALO_DO_TEXTO_DA_BARRA_S = 2;

// Ao vivo (`?ao-vivo`): outro arquivo, outra mensagem e outro ritmo; o resto da página é o mesmo.
const AO_VIVO = modoAoVivo(window.location.search);
const ARQUIVO_REPLAY = "dados/replay.json";
const ARQUIVO_DADOS = AO_VIVO ? ARQUIVO_AO_VIVO : ARQUIVO_REPLAY;
const ARQUIVO_MAPA = "vendor/countries-110m.json";
const MENSAGEM_SEM_DADOS = AO_VIVO ? MENSAGEM_SEM_DADOS_AO_VIVO : DICA_REPLAY;
// Ao vivo, enquanto o arquivo não existe (o serviço ainda está no baseline), a página tenta de novo a cada tanto.
const ESPERA_SEM_DADOS_MS = 10000;
const ATUALIZACAO_DO_SELO_MS = 1000;
const MENSAGEM_SEM_MAPA = "Falta web/vendor/countries-110m.json (ver web/vendor/README.md)";


// --- Elementos da página ---------------------------------------------------------------------------------

function pegarElementos() {
  const porId = (id) => document.getElementById(id);
  return {
    svg: porId("mapa-svg"),
    canvas: porId("mapa-canvas"),
    status: porId("status"),
    erro: porId("erro"),
    alerta: porId("alerta"),
    aviso: porId("aviso"),
    relogioTitulo: porId("relogio-titulo"),
    relogioNota: porId("relogio-nota"),
    aoVivoSelo: porId("ao-vivo-selo"),
    comoLerOnde: porId("como-ler-onde"),
    placarPeriodo: porId("placar-periodo"),
    data: porId("relogio-data"),
    hora: porId("relogio-hora"),
    velocidades: porId("velocidades"),
    regioes: porId("regioes"),
    anuncio: porId("anuncio"),
    barra: porId("barra-tempo"),
    botao: porId("botao-tocar"),
    contaClasse: { OK: porId("conta-OK"), RISCO: porId("conta-RISCO"), FALHA: porId("conta-FALHA") },
    contaTotal: porId("conta-total"),
    contaGeral: porId("conta-geral"),
    contaTimeout: porId("conta-timeout"),
    modeloNome: porId("modelo-nome"),
    placar: {
      arvore: { acertos: porId("arvore-acertos"), conferidas: porId("arvore-conferidas"), pct: porId("arvore-pct") },
      persistencia: { acertos: porId("persistencia-acertos"), conferidas: porId("persistencia-conferidas"), pct: porId("persistencia-pct") },
    },
    feed: porId("feed"),
    soErros: porId("so-erros"),
    feedFiltrado: porId("feed-filtrado"),
    legenda: porId("legenda"),
    cartao: { raiz: porId("detalhe-trecho"), tipo: porId("detalhe-tipo"), nome: porId("detalhe-nome"), km: porId("detalhe-km") },
    fluxo: {
      raiz: porId("fluxo-cartao"),
      vazio: porId("fluxo-vazio"),
      escolha: porId("fluxo-escolha"),
      corpo: porId("fluxo-corpo"),
      fechar: porId("fluxo-fechar"),
      titulo: porId("fluxo-titulo"),
      opcao: porId("fluxo-opcao"),
      trechos: porId("fluxo-trechos"),
      km: porId("fluxo-km"),
      rtt: porId("fluxo-rtt"),
      hora: porId("fluxo-hora"),
      rttAtual: porId("fluxo-rtt-atual"),
      atual: porId("fluxo-atual"),
      previsto: porId("fluxo-previsto"),
      situacao: porId("fluxo-situacao"),
      conferida: porId("fluxo-conferida"),
    },
  };
}

// As cores das classes vivem só no CSS (variáveis `--ok`, `--risco`, `--falha`, `--tinta`...); o canvas as lê daqui.
function lerCoresDoCss() {
  const estilo = getComputedStyle(document.documentElement);
  const cor = (nome) => estilo.getPropertyValue(nome).trim();
  return { OK: cor("--ok"), RISCO: cor("--risco"), FALHA: cor("--falha"), tinta: cor("--tinta"), papel: cor("--papel"), acao: cor("--acao") };
}

// --- Carregar dados --------------------------------------------------------------------------------------

async function carregarJson(url) {
  // `no-cache` = o navegador pergunta ao servidor se o arquivo mudou: o `replay.json` é regravado a cada `replay`.
  const resposta = await fetch(url, { cache: "no-cache" });
  if (!resposta.ok) {
    throw new Error(`${url}: HTTP ${resposta.status}`);
  }
  return resposta.json();
}

// Devolve o JSON, ou mostra a mensagem na página e devolve null se o arquivo não carregar.
async function carregarOuMostrarErro(url, mensagem, elementos) {
  try {
    return await carregarJson(url);
  } catch (erro) {
    console.error(erro);
    mostrarErro(elementos, mensagem);
    return null;
  }
}

function mostrarErro(elementos, mensagem) {
  elementos.status.hidden = true; // "Carregando..." não faz mais sentido
  elementos.erro.textContent = mensagem;
  elementos.erro.hidden = false;
}

// --- Estado ----------------------------------------------------------------------------------------------

// O estado é um objeto simples, passado de função em função. `tempo` (de tempo.js) guarda tudo o que é função do
// relógio (placar, contadores, posição); o resto é escolha de quem usa a página (velocidade, filtros, fluxo aberto).
function criarEstado(replay) {
  const regioes = regioesDosFluxos(replay.fluxos);
  return {
    tempo: criarTempo(replay), // valida o JSON; lança erro com a dica de `replay` se for de versão antiga
    fluxos: replay.fluxos,
    rotulos: replay.fluxos.map(rotuloDoFluxo),
    tocando: false,
    velocidade: AO_VIVO ? 1 : VELOCIDADE_INICIAL, // ao vivo o relógio anda em tempo real
    aoVivo: AO_VIVO,
    atrasoS: replay.meta.atraso_s ?? 0, // só ao vivo: quanto o relógio fica atrás da hora real (ver aovivo.js)
    geradoEmS: replay.meta.gerado_em_s ?? null, // só ao vivo: quando o serviço gravou o arquivo que a página tem
    intervaloDoServicoS: replay.meta.intervalo_s ?? 60,
    relogioDaTela: 0, // segundos reais de animação (relógio dos pulsos); ver `animacaoAnda`
    todasAsRegioes: regioes,
    regioesLigadas: new Set(regioes), // filtro por região: começa com todas
    visivel: replay.fluxos.map(() => true), // por fluxo: a região dele está ligada?
    soErros: false, // o feed mostra só as previsões erradas (desligado: a pessoa vê acertos e erros)
    selecionado: null, // índice do fluxo com o cartão aberto, ou null
    origemDoFoco: null, // o elemento que abriu o cartão (selo, linha do feed ou lista): o Esc devolve o foco a ele
    situacaoAnunciada: "pausado", // "pausado", "tocando" ou "fim": o último estado do relógio que o leitor de tela ouviu
    textoDaBarra: "", // o último `aria-valuetext` escrito na barra, e quando (relógio da animação)
    quandoDoTextoDaBarra: -Infinity,
    arrastando: false, // o ponteiro está na barra de tempo
    versaoDoFiltro: 0, // sobe quando o filtro do feed muda (região ou "só erros"), para o feed ser refeito
  };
}

// --- Relógio do replay -----------------------------------------------------------------------------------

// Pula o relógio para um instante qualquer (a barra de tempo e o botão Reiniciar). Tudo é recalculado do instante, sem
// soltar os pulsos das medições puladas: o mapa recebe só a última previsão de cada fluxo (para os selos).
function irParaInstante(estado, mapa, instante) {
  irParaTempo(estado.tempo, instante);
  mapa.restaurar(ultimasMedicoes(estado));
  if (terminou(estado.tempo) && !estado.aoVivo) {
    estado.tocando = false;
  }
}

// A última medição de cada fluxo até o instante do relógio, ou null para o fluxo que ainda não mediu.
function ultimasMedicoes(estado) {
  const { tempo } = estado;
  return estado.fluxos.map((_, f) => {
    const indice = ultimaDoFluxo(tempo, f);
    return indice < 0 ? null : tempo.medicoes[indice];
  });
}

// O relógio da animação (dos pulsos) é separado do estado "tocando". Ele anda enquanto toca e também depois do
// fim do replay, para os pulsos em voo terminarem; só o botão Pausar o congela (pausar congela os pulsos de propósito).
function animacaoAnda(estado) {
  return estado.tocando || terminou(estado.tempo);
}

// Avança o relógio do replay e solta os pulsos das medições que "aconteceram" neste quadro (na ordem do JSON); as
// previsões que o relógio acabou de conferir viram ✓ ou ✗ no selo do fluxo.
function avancarRelogio(estado, mapa, segundosReais) {
  const { tempo } = estado;
  let instante = tempo.agora + segundosReais * estado.velocidade;
  if (estado.aoVivo) {
    // Ao vivo o relógio segue a hora real (menos o atraso). Se ficou muito para trás (aba escondida), pula em vez de soltar
    // centenas de pulsos de uma vez.
    // O relógio nunca passa da última medição que a página tem (`tempo.fim`): o salto é medido até onde ele PODE ir. Sem isto, com os
    // dados parados há mais de SALTO_MAXIMO_S, `agora` voltaria a `fim` e o salto repetiria a cada quadro.
    const alvo = Math.min(instanteDoRelogio(Date.now(), estado.atrasoS), tempo.fim);
    if (alvo - tempo.agora > SALTO_MAXIMO_S) {
      irParaInstante(estado, mapa, alvo);
      return;
    }
    instante = alvo;
  }
  const { soltas, conferidas } = avancarTempo(tempo, instante);
  for (const indice of soltas) {
    mapa.soltarPulso(tempo.medicoes[indice], estado.relogioDaTela);
  }
  const duracao = mapa.duracaoDoVeredito(estado.velocidade, tempo.intervaloTipicoS);
  for (const medicao of conferidas) {
    mapa.marcarConferencia(medicao.f, acertou(medicao), estado.relogioDaTela, duracao);
  }
  // No fim o relógio para na última medição, em vez de seguir adiante. Ao vivo não há fim: ele espera a próxima consulta.
  if (terminou(tempo) && !estado.aoVivo) {
    estado.tocando = false;
  }
}

// Tocar / pausar; depois do fim, o mesmo botão recomeça do início.
function alternarTocar(estado, mapa) {
  if (terminou(estado.tempo)) {
    irParaInstante(estado, mapa, estado.tempo.inicio);
    estado.tocando = true;
    return;
  }
  estado.tocando = !estado.tocando;
}

// --- Painel ---------------------------------------------------------------------------------------------

function textoDoBotao(estado) {
  if (terminou(estado.tempo)) {
    return "Reiniciar";
  }
  return estado.tocando ? "Pausar" : "Tocar";
}

// "2026-09-23 20:09:57 UTC": a data e a hora da barra de tempo, como o leitor de tela as lê.
function textoDoInstante(segundos) {
  const { data, hora } = formatarInstante(segundos);
  return `${data} ${hora} UTC`;
}

// Escreve o `aria-valuetext` da barra (a data e a hora, em vez do número de segundos). Parado, vale na hora; tocando, só de
// 2 em 2 segundos reais, para o leitor de tela não anunciar a cada quadro.
function atualizarTextoDaBarra(estado, elementos) {
  const texto = textoDoInstante(estado.tempo.agora);
  const jaPassouTempo = estado.relogioDaTela - estado.quandoDoTextoDaBarra >= INTERVALO_DO_TEXTO_DA_BARRA_S;
  if (texto !== estado.textoDaBarra && (!estado.tocando || jaPassouTempo)) {
    elementos.barra.setAttribute("aria-valuetext", texto);
    estado.textoDaBarra = texto;
    estado.quandoDoTextoDaBarra = estado.relogioDaTela;
  }
}

function atualizarPainel(estado, elementos) {
  const { tempo } = estado;
  const { data, hora } = formatarInstante(tempo.agora);
  elementos.data.textContent = data;
  elementos.hora.textContent = hora;
  for (const classe of tempo.classes) {
    elementos.contaClasse[classe].textContent = tempo.contagem[classe];
  }
  elementos.contaTotal.textContent = tempo.proxima;
  elementos.contaTimeout.textContent = tempo.timeouts;
  if (estado.aoVivo) {
    return; // ao vivo não há botão nem barra de tempo
  }
  elementos.botao.textContent = textoDoBotao(estado);
  // A barra acompanha o relógio, menos enquanto o ponteiro a segura (senão o relógio brigaria com a mão). No fim do replay o
  // polegar vai para o fim da barra: o `max` dela fica até um passo depois do fim (ver `montarBarra`), e o valor do relógio
  // cairia no passo anterior, com o polegar "voltando" alguns segundos depois de `End` ou de arrastar até o fim.
  if (!estado.arrastando) {
    elementos.barra.value = terminou(tempo) ? elementos.barra.max : Math.floor(tempo.agora);
  }
  atualizarTextoDaBarra(estado, elementos);
}

// --- Aviso para o leitor de tela ------------------------------------------------------------------------

// Escreve no `aria-live` (fora da tela). Só quando algo importante muda, nunca a cada quadro.
function anunciar(elementos, texto) {
  elementos.anuncio.textContent = texto;
}

// O placar em uma frase: "Quanto o sistema acertou: 6733 de 8099 (83,1 %); palpite simples: 6567 de 8099 (81,1 %)."
function frasePlacar(estado) {
  const { placar } = estado.tempo;
  const arvore = `${placar.acertosArvore} de ${placar.conferidas} (${formatarPorcentagem(placar.acertosArvore, placar.conferidas)})`;
  const persistencia = `${placar.acertosPersistencia} de ${placar.conferidas} (${formatarPorcentagem(placar.acertosPersistencia, placar.conferidas)})`;
  return `Quanto o sistema acertou: ${arvore}; palpite simples (tudo igual a agora): ${persistencia}.`;
}

// Anuncia quando o replay passa a tocar, é pausado ou chega ao fim (e o placar nessas duas últimas).
function anunciarMudancaDoRelogio(estado, elementos) {
  if (estado.aoVivo) {
    return; // ao vivo o relógio nunca "para" nem "termina": nada a anunciar
  }
  const situacao = terminou(estado.tempo) ? "fim" : estado.tocando ? "tocando" : "pausado";
  if (situacao === estado.situacaoAnunciada) {
    return;
  }
  estado.situacaoAnunciada = situacao;
  const hora = textoDoInstante(estado.tempo.agora);
  const frases = {
    tocando: `Simulação tocando a ${estado.velocidade} vezes a velocidade real.`,
    pausado: `Simulação pausada em ${hora}. ${frasePlacar(estado)}`,
    fim: `Fim da simulação em ${hora}. ${frasePlacar(estado)}`,
  };
  anunciar(elementos, frases[situacao]);
}

// --- Controles: velocidade, barra de tempo e regiões -------------------------------------------------------

// Um botão por velocidade; o escolhido fica "apertado" (aria-pressed, e o CSS o destaca).
function montarVelocidades(estado, elementos) {
  const botoes = VELOCIDADES.map((velocidade) => {
    const botao = criarCelula("button", NOMES_DAS_VELOCIDADES[velocidade], "botao-velocidade");
    botao.type = "button";
    botao.title = `${velocidade} vezes a velocidade real: 1 minuto na tela = ${velocidade} minutos da simulação`;
    botao.addEventListener("click", () => {
      estado.velocidade = velocidade;
      marcarVelocidade();
    });
    elementos.velocidades.append(botao);
    return botao;
  });

  function marcarVelocidade() {
    botoes.forEach((botao, i) => botao.setAttribute("aria-pressed", String(VELOCIDADES[i] === estado.velocidade)));
  }
  marcarVelocidade();
}

// A barra vai do início ao fim do replay (em segundos UTC), de PASSO_DA_BARRA_S em PASSO_DA_BARRA_S. Mexer nela pula o
// relógio para aquele instante. O navegador só aceita valores `min + n x passo`: se o `max` fosse o fim exato, o último
// valor possível ficaria até um passo antes do fim e o placar final seria inalcançável pela barra. Por isso o `max`
// sobe até o próximo passo; o relógio nunca passa do fim (`irParaTempo` limita).
function montarBarra(estado, mapa, elementos) {
  const { barra } = elementos;
  const { inicio, fim } = estado.tempo;
  barra.step = PASSO_DA_BARRA_S;
  barra.min = inicio;
  barra.max = inicio + Math.ceil((fim - inicio) / PASSO_DA_BARRA_S) * PASSO_DA_BARRA_S;
  barra.value = estado.tempo.agora;
  barra.disabled = false;
  barra.addEventListener("input", () => irParaInstante(estado, mapa, Number(barra.value)));
  barra.addEventListener("pointerdown", () => (estado.arrastando = true));
  for (const evento of ["pointerup", "pointercancel", "blur"]) {
    barra.addEventListener(evento, () => (estado.arrastando = false));
  }
}

// Uma caixa por região que existe nos dados. Desligar uma esconde os fluxos dela no mapa (rotas, pulsos e selos); o
// placar e a matriz continuam contando todos os fluxos (os títulos deles dizem isso).
function montarRegioes(estado, mapa, elementos, selecionar) {
  for (const regiao of estado.todasAsRegioes) {
    const rotulo = document.createElement("label");
    rotulo.className = "regiao";
    const caixa = document.createElement("input");
    caixa.type = "checkbox";
    caixa.checked = true;
    caixa.addEventListener("change", () => {
      if (caixa.checked) {
        estado.regioesLigadas.add(regiao);
      } else {
        estado.regioesLigadas.delete(regiao);
      }
      aplicarFiltroDeRegioes(estado, mapa, elementos, selecionar);
    });
    rotulo.append(caixa, regiao);
    elementos.regioes.append(rotulo);
  }
}

function aplicarFiltroDeRegioes(estado, mapa, elementos, selecionar) {
  estado.visivel = estado.fluxos.map((fluxo) => estado.regioesLigadas.has(fluxo.regiao));
  mapa.definirVisiveis(estado.visivel);
  estado.versaoDoFiltro += 1;
  elementos.feedFiltrado.hidden = estado.regioesLigadas.size === estado.todasAsRegioes.length;
  // O cartão de um fluxo cuja região foi desligada fecha: a rota dele nem está mais no mapa.
  if (estado.selecionado !== null && !estado.visivel[estado.selecionado]) {
    selecionar(null);
  }
}


// --- Cartão do fluxo --------------------------------------------------------------------------------------

// Abre o cartão do fluxo `f` (ou fecha, com null) e destaca a rota dele no mapa.
function selecionarFluxo(estado, mapa, f) {
  estado.selecionado = f;
  mapa.definirSelecionado(f);
}

// Uma opção por fluxo, na ordem do JSON, para abrir o cartão sem usar o mapa (o toque e o teclado no mapa são difíceis
// em tela pequena, e o leitor de tela anuncia a lista inteira). O texto de cada opção é o rótulo do fluxo.
function montarEscolhaDeFluxo(estado, elementos, selecionar) {
  const { escolha } = elementos.fluxo;
  estado.rotulos.forEach((rotulo, f) => {
    const opcao = document.createElement("option");
    opcao.value = String(f);
    opcao.textContent = rotulo;
    escolha.append(opcao);
  });
  escolha.addEventListener("change", () => {
    if (escolha.value !== "") {
      selecionar(Number(escolha.value), escolha, true);
      escolha.value = ""; // de volta ao "Escolher...": o cartão é que mostra o fluxo aberto
    }
  });
}

// O elemento visível ao qual o foco deve voltar quando o cartão fecha: quem o abriu; se ele sumiu (região desligada, por
// exemplo), o selo do fluxo; se nem esse existe, nenhum.
function elementoParaDevolverOFoco(estado, mapa, f) {
  const visivel = (elemento) => elemento !== null && elemento.isConnected && elemento.getClientRects().length > 0;
  if (visivel(estado.origemDoFoco)) {
    return estado.origemDoFoco;
  }
  const selo = mapa.alvoDoSelo(f);
  return visivel(selo) ? selo : null;
}

// --- Laço de animação -----------------------------------------------------------------------------------

// Um quadro: avança a animação e o relógio (conforme o estado), desenha os pulsos e atualiza o painel.
function iniciarLaco(estado, mapa, elementos, partes) {
  let ultimoQuadro = null;
  let ultimaFalha = null; // mensagem do último erro mostrado, para não repetir 60 vezes por segundo

  function quadro(agoraMs) {
    // O próximo quadro é pedido ANTES do trabalho: se algo abaixo lançar uma exceção, a animação não morre em silêncio.
    requestAnimationFrame(quadro);
    const decorrido = ultimoQuadro === null ? 0 : (agoraMs - ultimoQuadro) / 1000;
    ultimoQuadro = agoraMs;
    const segundos = Math.max(0, Math.min(decorrido, TEMPO_MAXIMO_DO_QUADRO_S));
    try {
      if (animacaoAnda(estado)) {
        estado.relogioDaTela += segundos;
      }
      if (estado.tocando) {
        avancarRelogio(estado, mapa, segundos);
      }
      mapa.desenhar(estado.relogioDaTela);
      atualizarPainel(estado, elementos);
      atualizarPlacarSeMudou(estado, elementos, partes);
      atualizarCartao(estado, elementos, partes);
      anunciarMudancaDoRelogio(estado, elementos);
    } catch (erro) {
      if (erro.message !== ultimaFalha) {
        ultimaFalha = erro.message;
        console.error(erro);
        mostrarErro(elementos, `Erro na animação: ${erro.message}`);
      }
    }
  }

  requestAnimationFrame(quadro);
}

// Em todo carregamento: confere se alguma rota cruza a borda (o "corte") da projeção. Se cruzar, a linha atravessa o
// mapa de um lado a outro; isso não impede a página de funcionar, então é um alerta (console e página), não um erro.
function conferirCorteNoCarregamento(mapa, elementos) {
  const { rotas, pares, saltos } = mapa.conferirCorte();
  if (saltos === 0) {
    return;
  }
  const mensagem = `Atenção: ${saltos} de ${pares} segmentos das ${rotas} rotas cruzam a borda do mapa (as rotas mudaram?). Ajuste ROTACAO em mapa.js.`;
  console.warn(mensagem);
  elementos.alerta.textContent = mensagem;
  elementos.alerta.hidden = false;
}

// Controles que usam o Espaço para si (apertar o botão, marcar a caixa, abrir a lista): neles o atalho de tocar / pausar
// não age. A barra de tempo não usa o Espaço, então ali ele toca e pausa.
const USAM_O_ESPACO = 'button, select, textarea, a[href], [role="button"], input:not([type="range"])';

// Atalhos de teclado da página: Esc fecha o cartão do fluxo (e devolve o foco a quem o abriu); Espaço toca e pausa.
// As setas e Enter dos selos ficam em foco.js e selos.js.
function ligarTeclado(estado, mapa, fecharCartao) {
  document.addEventListener("keydown", (evento) => {
    if (evento.defaultPrevented) {
      return; // alguém (um selo, a barra) já tratou a tecla
    }
    if (evento.key === "Escape" && estado.selecionado !== null) {
      fecharCartao();
    }
    const semModificador = !evento.altKey && !evento.ctrlKey && !evento.metaKey && !evento.shiftKey;
    if (evento.key === " " && !evento.repeat && semModificador && !evento.target.closest(USAM_O_ESPACO)) {
      evento.preventDefault(); // Espaço não rola a página
      alternarTocar(estado, mapa);
    }
  });
}

// --- Ao vivo --------------------------------------------------------------------------------------------

// Troca os textos que só valem para o replay: o aviso da rota, o título do relógio, "aparelhos no Brasil" e o período do placar.
// Tudo com textContent. Os textos longos vêm do JSON (`meta.aviso`) ou daqui; nada vira HTML.
function aplicarTextosAoVivo(elementos, meta) {
  document.body.classList.add("ao-vivo");
  elementos.aviso.textContent = meta.aviso;
  elementos.relogioTitulo.firstChild.nodeValue = "Relógio ao vivo ";
  elementos.relogioNota.textContent = `· hora UTC, ${Math.round(meta.atraso_s / 60)} min atrás da hora real`;
  elementos.comoLerOnde.textContent = "Aparelhos na América Latina";
  elementos.placarPeriodo.textContent =
    `Ao vivo: pontos de medição que não estão no treino do modelo, lidos na API do RIPE Atlas${meta.janela_h ? ` (últimas ${meta.janela_h} h)` : ""}. ` +
    "Só entram previsões já conferidas (12 min depois); no começo são poucas.";
}

// A faixa "ao vivo" do relógio: há quanto tempo o serviço gravou o arquivo, e o aviso de que ele pode ter parado.
function escreverSeloAoVivo(estado, elementos) {
  const idade = Math.max(0, Date.now() / 1000 - estado.geradoEmS);
  const parado = servicoParado(idade, estado.intervaloDoServicoS);
  elementos.aoVivoSelo.textContent = parado
    ? `● O serviço parou? Dados de ${textoDaIdade(idade)}. Rode: uv run python -m preditor aovivo`
    : `● Ao vivo · dados de ${textoDaIdade(idade)}`;
  elementos.aoVivoSelo.classList.toggle("ao-vivo-parado", parado);
}

// Relê o arquivo e troca o relógio de dados SEM mexer no instante em que a página está: as medições que já passaram contam sem
// pulso, as seguintes saem quando o relógio chegar nelas. Se a lista de conexões mudou (o serviço foi recomeçado), recarrega.
async function atualizarDadosAoVivo(estado, elementos, partes) {
  let novo;
  try {
    novo = await carregarJson(ARQUIVO_AO_VIVO);
  } catch (erro) {
    console.warn(erro); // sem arquivo agora: o selo passa a avisar que os dados envelhecem
    return;
  }
  if (novo.meta.gerado_em_s === estado.geradoEmS) {
    return; // o serviço ainda não regravou
  }
  if (!mesmosFluxos(estado.fluxos, novo.fluxos)) {
    window.location.reload();
    return;
  }
  const antes = estado.tempo.agora;
  estado.tempo = criarTempo(novo); // valida; se o arquivo estiver fora do formato, o erro aparece na página
  irParaTempo(estado.tempo, antes);
  estado.geradoEmS = novo.meta.gerado_em_s;
  partes.cartao.chave = null; // os índices das medições mudaram: o cartão da conexão se reescreve
  elementos.contaGeral.textContent = novo.medicoes.length;
}

function prepararAoVivo(estado, mapa, elementos, partes, replay) {
  aplicarTextosAoVivo(elementos, replay.meta);
  // O botão de tocar fica escondido (o CSS), mas habilitado: é o sinal que o verificar-carga.js lê para saber que a página carregou.
  elementos.botao.disabled = false;
  // Começa na hora real (menos o atraso): quem abre a página vê o estado de agora, não o começo do serviço.
  irParaInstante(estado, mapa, instanteDoRelogio(Date.now(), estado.atrasoS));
  estado.tocando = true;
  escreverSeloAoVivo(estado, elementos);
  setInterval(() => escreverSeloAoVivo(estado, elementos), ATUALIZACAO_DO_SELO_MS);
  setInterval(() => atualizarDadosAoVivo(estado, elementos, partes).catch((erro) => mostrarErro(elementos, `Erro: ${erro.message}`)), (replay.meta.atualizacao_s ?? 30) * 1000);
}

// --- Início ---------------------------------------------------------------------------------------------

// Marca na barra lateral o modo em que a página está (`aria-current` também avisa o leitor de tela).
function marcarModoNoMenu() {
  const atual = document.getElementById(AO_VIVO ? "menu-ao-vivo" : "menu-replay");
  atual.setAttribute("aria-current", "page");
}

async function principal() {
  marcarModoNoMenu();
  const elementos = pegarElementos();

  // Cada arquivo tem a sua mensagem: o replay vem do comando em Python; o mapa-base vem da cópia local em vendor/.
  let replay = await carregarOuMostrarErro(ARQUIVO_DADOS, MENSAGEM_SEM_DADOS, elementos);
  // Ao vivo o arquivo só existe depois da primeira consulta do serviço: a página espera, em vez de ficar parada no erro.
  while (AO_VIVO && replay === null) {
    await new Promise((resolver) => setTimeout(resolver, ESPERA_SEM_DADOS_MS));
    replay = await carregarOuMostrarErro(ARQUIVO_DADOS, MENSAGEM_SEM_DADOS, elementos);
  }
  const topologia = await carregarOuMostrarErro(ARQUIVO_MAPA, MENSAGEM_SEM_MAPA, elementos);
  if (replay === null || topologia === null) {
    return; // a mensagem de erro já está na página
  }
  elementos.erro.hidden = true; // ao vivo, a mensagem de "ainda sem dados" sai quando o arquivo aparece

  const estado = criarEstado(replay);
  elementos.status.hidden = true;
  elementos.contaGeral.textContent = replay.medicoes.length;
  // O modelo que faz as previsões (o JSON traz o nome e o nº de árvores; a página só escreve o texto).
  elementos.modeloNome.textContent = `${replay.modelo.nome}, ${replay.modelo.arvores} árvores`;

  // `mapa` só existe depois de `criarMapa`, mas o clique no selo precisa dele: a função abaixo o lê no momento do clique.
  let mapa = null;
  // Feed e cartão são montados uma vez; `desenhado` lembra o que o painel já mostra (ver `atualizarPlacarSeMudou`).
  const partes = {
    feed: null, // montado abaixo: precisa de `selecionar`
    desenhado: { placar: null, proxima: -1, filtro: -1 },
    cartao: { chave: null, fluxo: null },
  };

  // Abre o cartão do fluxo `f` (ou fecha, com null). `origem` é o elemento que o abriu (selo, linha do feed ou lista);
  // `porTeclado`: o foco vai para o cartão, para o leitor de tela lê-lo e o Esc o fechar. O cartão é reescrito na hora
  // (não no próximo quadro) para o foco já cair num elemento visível.
  function selecionar(f, origem = null, porTeclado = false) {
    estado.origemDoFoco = f === null ? estado.origemDoFoco : origem;
    selecionarFluxo(estado, mapa, f);
    atualizarCartao(estado, elementos, partes);
    elementos.fluxo.raiz.setAttribute("aria-label", f === null ? "Conexão selecionada" : `Conexão selecionada: ${estado.rotulos[f]}`);
    if (f !== null) {
      if (porTeclado) {
        elementos.fluxo.raiz.focus();
      }
      // Em tela estreita o cartão fica abaixo do mapa: leva-o à vista, sem rolar se já está inteiro na tela.
      elementos.fluxo.raiz.scrollIntoView({ block: "nearest" });
    }
  }

  // Fecha o cartão (Esc ou o botão ×). Se o foco estava nele (ou se perdeu com o clique no ×), volta para quem o abriu.
  function fecharCartao() {
    const f = estado.selecionado;
    const foco = document.activeElement;
    const focoNoCartao = foco === document.body || elementos.fluxo.raiz.contains(foco);
    selecionar(null);
    anunciar(elementos, "Detalhes da conexão fechados.");
    const destino = focoNoCartao ? elementoParaDevolverOFoco(estado, mapa, f) : null;
    if (destino !== null) {
      destino.focus();
    }
  }

  // As cores vêm do CSS; o movimento reduzido (prefers-reduced-motion) tira o rastro dos pulsos.
  const semRastro = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  mapa = criarMapa({
    svg: elementos.svg,
    canvas: elementos.canvas,
    topologia,
    fluxos: replay.fluxos,
    cores: lerCoresDoCss(),
    cartao: elementos.cartao,
    raizDaLegenda: elementos.legenda,
    rotulos: estado.rotulos,
    aoSelecionar: selecionar,
    semRastro,
    rotacao: AO_VIVO ? ROTACAO_AO_VIVO : undefined,
  });
  conferirCorteNoCarregamento(mapa, elementos);
  partes.feed = montarFeed(elementos.feed, selecionar);

  if (!AO_VIVO) {
    montarVelocidades(estado, elementos);
    montarBarra(estado, mapa, elementos);
  }
  montarRegioes(estado, mapa, elementos, selecionar);
  montarEscolhaDeFluxo(estado, elementos, selecionar);
  elementos.soErros.checked = estado.soErros;
  elementos.soErros.addEventListener("change", () => {
    estado.soErros = elementos.soErros.checked;
    estado.versaoDoFiltro += 1;
  });
  elementos.fluxo.fechar.addEventListener("click", fecharCartao);
  ligarTeclado(estado, mapa, fecharCartao);

  if (AO_VIVO) {
    prepararAoVivo(estado, mapa, elementos, partes, replay);
  } else {
    elementos.botao.disabled = false;
    elementos.botao.addEventListener("click", () => alternarTocar(estado, mapa));
  }
  iniciarLaco(estado, mapa, elementos, partes);
}

// Qualquer falha que escape de `principal` (ex.: dado fora do formato) aparece na página, não só no console.
principal().catch((erro) => {
  console.error(erro);
  mostrarErro(pegarElementos(), `Erro: ${erro.message}`);
});
