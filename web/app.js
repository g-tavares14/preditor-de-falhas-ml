// app.js: relógio do replay, controles e teclado (SPEC-visualizacao.md).
//
// Lê `dados/replay.json` (gerado por `uv run python -m preditor replay`) e reproduz as medições em tempo acelerado.
// Quem faz o quê: mapa.js (e rotas.js, desenho.js, pulsos.js, selos.js, foco.js) desenha o mapa e os pulsos; tempo.js e
// placar.js fazem as contas do relógio e do placar (sem DOM, rodam em Node); painel.js monta o placar, a matriz e o feed;
// cartao.js, o cartão do fluxo; arvore.js (e caminho.js), o painel da árvore. Aqui não se calcula métrica nem rótulo: só se conta e se compara o que já vem no JSON.

import { atualizarArvore, montarArvore } from "./arvore.js";
import { atualizarCartao, montarColunasDoCartao } from "./cartao.js";
import { criarCelula, formatarInstante, rotuloDoFluxo } from "./comum.js";
import { criarMapa } from "./mapa.js";
import { atualizarPlacarSeMudou, formatarPorcentagem, montarFeed, montarMatriz } from "./painel.js";
import { acertou } from "./placar.js";
import { DICA_REPLAY, avancarTempo, criarTempo, irParaTempo, regioesDosFluxos, terminou, ultimaDoFluxo } from "./tempo.js";

// --- Constantes -----------------------------------------------------------------------------------------

// Velocidades oferecidas: quantos segundos DA SIMULAÇÃO passam a cada segundo real. A 300x as 12 h da validação duram
// cerca de 2 min 24 s; a 60x, 12 min; a 900x, 48 s. Se subir o maior valor, rever `MAXIMO_DE_PULSOS` em mapa.js.
const VELOCIDADES = [60, 300, 900];
const VELOCIDADE_INICIAL = 300;

// Se a aba ficar escondida, o navegador pausa a animação; ao voltar, o primeiro quadro teria um salto enorme.
// Limitar o tempo de cada quadro evita soltar milhares de pulsos de uma vez.
const TEMPO_MAXIMO_DO_QUADRO_S = 0.1;

// A barra de tempo anda de 1 em 1 minuto (as setas do teclado) e o leitor de tela lê a hora dela de 2 em 2 segundos no
// máximo enquanto o replay toca (decisão de acessibilidade: ler a cada quadro seria uma enxurrada de anúncios).
const PASSO_DA_BARRA_S = 60;
const INTERVALO_DO_TEXTO_DA_BARRA_S = 2;

const ARQUIVO_REPLAY = "dados/replay.json";
const ARQUIVO_MAPA = "vendor/countries-110m.json";
const MENSAGEM_SEM_DADOS = DICA_REPLAY;
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
    data: porId("relogio-data"),
    hora: porId("relogio-hora"),
    velocidade: porId("velocidade"),
    velocidades: porId("velocidades"),
    regioes: porId("regioes"),
    anuncio: porId("anuncio"),
    barra: porId("barra-tempo"),
    botao: porId("botao-tocar"),
    contaClasse: { OK: porId("conta-OK"), RISCO: porId("conta-RISCO"), FALHA: porId("conta-FALHA") },
    contaTotal: porId("conta-total"),
    contaGeral: porId("conta-geral"),
    contaTimeout: porId("conta-timeout"),
    contaSemFuturo: porId("conta-sem-futuro"),
    placar: {
      arvore: { acertos: porId("arvore-acertos"), conferidas: porId("arvore-conferidas"), pct: porId("arvore-pct") },
      persistencia: { acertos: porId("persistencia-acertos"), conferidas: porId("persistencia-conferidas"), pct: porId("persistencia-pct") },
    },
    matriz: porId("matriz"),
    feed: porId("feed"),
    soErros: porId("so-erros"),
    feedFiltrado: porId("feed-filtrado"),
    arvore: { seletor: porId("arvore-seletor"), situacao: porId("arvore-situacao"), svg: porId("arvore-svg"), passos: porId("arvore-passos"), regra: porId("arvore-regra") },
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
      folha: porId("fluxo-folha"),
      x: porId("fluxo-x"),
      regra: porId("fluxo-regra"),
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
    colunas: replay.colunas,
    regras: replay.regras,
    arvores: replay.arvores, // o painel da árvore: estrutura e regras da oficial e da ajustada
    // As colunas que a ajustada tem a mais que a oficial (os valores delas vêm em `x_ajuste`, nessa ordem).
    colunasAjuste: replay.arvores.ajustada.colunas.filter((coluna) => !replay.colunas.includes(coluna)),
    arvoreEscolhida: "oficial", // a árvore do painel (o resto da página segue sempre a oficial)
    rotulos: replay.fluxos.map(rotuloDoFluxo),
    tocando: false,
    velocidade: VELOCIDADE_INICIAL,
    relogioDaTela: 0, // segundos reais de animação (relógio dos pulsos); ver `animacaoAnda`
    todasAsRegioes: regioes,
    regioesLigadas: new Set(regioes), // filtro por região: começa com todas
    visivel: replay.fluxos.map(() => true), // por fluxo: a região dele está ligada?
    soErros: true, // o feed mostra só as previsões erradas
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
  if (terminou(estado.tempo)) {
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
  const { soltas, conferidas } = avancarTempo(tempo, tempo.agora + segundosReais * estado.velocidade);
  for (const indice of soltas) {
    mapa.soltarPulso(tempo.medicoes[indice], estado.relogioDaTela);
  }
  const duracao = mapa.duracaoDoVeredito(estado.velocidade, tempo.intervaloTipicoS);
  for (const medicao of conferidas) {
    mapa.marcarConferencia(medicao.f, acertou(medicao), estado.relogioDaTela, duracao);
  }
  // No fim o relógio para na última medição, em vez de seguir adiante.
  if (terminou(tempo)) {
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
  elementos.contaSemFuturo.textContent = tempo.semFuturo;
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

// O placar em uma frase: "Árvore 6733 de 8099 (83,1 %); persistência 6567 de 8099 (81,1 %)."
function frasePlacar(estado) {
  const { placar } = estado.tempo;
  const arvore = `${placar.acertosArvore} de ${placar.conferidas} (${formatarPorcentagem(placar.acertosArvore, placar.conferidas)})`;
  const persistencia = `${placar.acertosPersistencia} de ${placar.conferidas} (${formatarPorcentagem(placar.acertosPersistencia, placar.conferidas)})`;
  return `Placar: árvore ${arvore}; persistência ${persistencia}.`;
}

// Anuncia quando o replay passa a tocar, é pausado ou chega ao fim (e o placar nessas duas últimas).
function anunciarMudancaDoRelogio(estado, elementos) {
  const situacao = terminou(estado.tempo) ? "fim" : estado.tocando ? "tocando" : "pausado";
  if (situacao === estado.situacaoAnunciada) {
    return;
  }
  estado.situacaoAnunciada = situacao;
  const hora = textoDoInstante(estado.tempo.agora);
  const frases = {
    tocando: `Replay tocando a ${estado.velocidade} vezes.`,
    pausado: `Replay pausado em ${hora}. ${frasePlacar(estado)}`,
    fim: `Fim do replay em ${hora}. ${frasePlacar(estado)}`,
  };
  anunciar(elementos, frases[situacao]);
}

// --- Controles: velocidade, barra de tempo e regiões -------------------------------------------------------

// Um botão por velocidade; o escolhido fica "apertado" (aria-pressed, e o CSS o destaca) e a velocidade aparece no título.
function montarVelocidades(estado, elementos) {
  const botoes = VELOCIDADES.map((velocidade) => {
    const botao = criarCelula("button", `${velocidade}×`, "botao-velocidade");
    botao.type = "button";
    botao.addEventListener("click", () => {
      estado.velocidade = velocidade;
      marcarVelocidade();
    });
    elementos.velocidades.append(botao);
    return botao;
  });

  function marcarVelocidade() {
    botoes.forEach((botao, i) => botao.setAttribute("aria-pressed", String(VELOCIDADES[i] === estado.velocidade)));
    elementos.velocidade.textContent = estado.velocidade;
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
      atualizarArvore(estado, elementos.arvore, partes.arvore);
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

// --- Início ---------------------------------------------------------------------------------------------

async function principal() {
  const elementos = pegarElementos();

  // Cada arquivo tem a sua mensagem: o replay vem do comando em Python; o mapa-base vem da cópia local em vendor/.
  const replay = await carregarOuMostrarErro(ARQUIVO_REPLAY, MENSAGEM_SEM_DADOS, elementos);
  const topologia = await carregarOuMostrarErro(ARQUIVO_MAPA, MENSAGEM_SEM_MAPA, elementos);
  if (replay === null || topologia === null) {
    return; // a mensagem de erro já está na página
  }

  const estado = criarEstado(replay);
  elementos.status.hidden = true;
  elementos.contaGeral.textContent = replay.medicoes.length;

  // `mapa` só existe depois de `criarMapa`, mas o clique no selo precisa dele: a função abaixo o lê no momento do clique.
  let mapa = null;
  // Matriz, feed e cartão são montados uma vez; `desenhado` lembra o que o painel já mostra (ver `atualizarPlacarSeMudou`).
  const partes = {
    matriz: montarMatriz(elementos.matriz, estado.tempo.classes),
    feed: null, // montado abaixo: precisa de `selecionar`
    desenhado: { placar: null, proxima: -1, filtro: -1 },
    cartao: { chave: null, fluxo: null, valoresDeX: montarColunasDoCartao(elementos.fluxo.x, estado.colunas) },
    arvore: montarArvore(elementos.arvore, replay, (chave) => (estado.arvoreEscolhida = chave)),
  };

  // Abre o cartão do fluxo `f` (ou fecha, com null). `origem` é o elemento que o abriu (selo, linha do feed ou lista);
  // `porTeclado`: o foco vai para o cartão, para o leitor de tela lê-lo e o Esc o fechar. O cartão é reescrito na hora
  // (não no próximo quadro) para o foco já cair num elemento visível.
  function selecionar(f, origem = null, porTeclado = false) {
    estado.origemDoFoco = f === null ? estado.origemDoFoco : origem;
    selecionarFluxo(estado, mapa, f);
    atualizarCartao(estado, elementos, partes);
    elementos.fluxo.raiz.setAttribute("aria-label", f === null ? "Fluxo selecionado" : `Fluxo selecionado: ${estado.rotulos[f]}`);
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
    anunciar(elementos, "Cartão do fluxo fechado.");
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
  });
  conferirCorteNoCarregamento(mapa, elementos);
  partes.feed = montarFeed(elementos.feed, selecionar);

  montarVelocidades(estado, elementos);
  montarBarra(estado, mapa, elementos);
  montarRegioes(estado, mapa, elementos, selecionar);
  montarEscolhaDeFluxo(estado, elementos, selecionar);
  elementos.soErros.checked = estado.soErros;
  elementos.soErros.addEventListener("change", () => {
    estado.soErros = elementos.soErros.checked;
    estado.versaoDoFiltro += 1;
  });
  elementos.fluxo.fechar.addEventListener("click", fecharCartao);
  ligarTeclado(estado, mapa, fecharCartao);

  elementos.botao.disabled = false;
  elementos.botao.addEventListener("click", () => alternarTocar(estado, mapa));
  iniciarLaco(estado, mapa, elementos, partes);
}

// Qualquer falha que escape de `principal` (ex.: dado fora do formato) aparece na página, não só no console.
principal().catch((erro) => {
  console.error(erro);
  mostrarErro(pegarElementos(), `Erro: ${erro.message}`);
});
