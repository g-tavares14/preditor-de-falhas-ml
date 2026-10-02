// tempo.js: o estado do replay como função do relógio (SPEC-visualizacao.md, "Comportamento da página").
//
// Lógica pura, sem DOM e sem d3: roda em Node sobre o `replay.json`. Aqui só se CONTA e se COMPARA o que já vem no
// JSON; nenhuma métrica do X nem rótulo é calculada.
//
// A regra que organiza tudo: o estado depende só do instante `agora`, nunca do caminho até ele. Há dois caminhos:
//   - `avancarTempo`: o replay tocando, de um quadro ao seguinte (só para a frente);
//   - `irParaTempo`: pular para qualquer instante (para a frente ou para trás), recalculando do zero.
// Os dois usam as mesmas funções de soma (`somarMedicao` aqui e `somarConferencia` em placar.js), então tocar até T e
// pular para T dão exatamente o mesmo placar, matriz, contadores e "última medição de cada fluxo".

import { DICA_REPLAY, conferirAte, listarConferencias, placarAte } from "./placar.js";

// --- Validação do JSON -----------------------------------------------------------------------------------

// As classes que a página sabe colorir (variáveis `--ok`, `--risco` e `--falha` no estilo.css, os chips, os selos e os
// pulsos). O JSON tem de trazer exatamente este conjunto: uma classe nova sairia sem cor, e uma que faltasse deixaria a
// matriz com linha ou coluna a menos. A ORDEM é a do JSON (`meta.classes`): é ela que monta a matriz.
const CLASSES_COLORIDAS = ["OK", "RISCO", "FALHA"];

function exigir(condicao, mensagem) {
  if (!condicao) {
    throw new Error(`replay.json fora do formato: ${mensagem}. ${DICA_REPLAY}`);
  }
}

const ehNumeroOuNulo = (valor) => valor === null || Number.isFinite(valor);

// Confere o que a página lê de cada medição e de cada fluxo. Um arquivo de versão antiga (sem `x`, `folha`, `t_futuro`
// ou `mediana_ms`) para aqui, com a dica de gerar o JSON de novo, em vez de mostrar um painel pela metade.
// (O desenho das rotas tem a sua própria validação, em desenho.js.)
function validarReplay(replay) {
  const { meta, colunas, regras, fluxos, medicoes } = replay;
  exigir(meta && Array.isArray(meta.classes) && meta.classes.length > 0, "falta `meta.classes`");
  const classesIguais = meta.classes.length === CLASSES_COLORIDAS.length && CLASSES_COLORIDAS.every((classe) => meta.classes.includes(classe));
  if (!classesIguais) {
    // Sem a dica de gerar o JSON de novo: regerar não conserta uma classe que a página não conhece.
    throw new Error(`replay.json fora do formato: \`meta.classes\` é [${meta.classes.join(", ")}], mas a página só sabe colorir exatamente [${CLASSES_COLORIDAS.join(", ")}] (classe desconhecida, faltando ou repetida)`);
  }
  exigir(Array.isArray(colunas) && colunas.length > 0 && colunas.every((c) => typeof c === "string"), "falta `colunas`");
  exigir(regras !== null && typeof regras === "object", "falta `regras`");
  exigir(Array.isArray(fluxos) && fluxos.length > 0, "a lista de fluxos está vazia");
  exigir(Array.isArray(medicoes) && medicoes.length > 0, "a lista de medições está vazia");

  fluxos.forEach((fluxo, i) => {
    const onde = `fluxo ${i}`;
    exigir(typeof fluxo.id === "string" && typeof fluxo.regiao === "string" && typeof fluxo.pais === "string", `${onde}: falta id, regiao ou pais`);
    exigir(typeof fluxo.opcao === "string" && Number.isFinite(fluxo.km), `${onde}: falta opcao ou km`);
    exigir(Number.isFinite(fluxo.rtt_minimo_ms), `${onde}: falta rtt_minimo_ms`);
    exigir(ehNumeroOuNulo(fluxo.mediana_ms) && fluxo.mediana_ms !== undefined, `${onde}: falta mediana_ms`);
  });

  const classes = meta.classes;
  medicoes.forEach((m, i) => {
    const onde = `medição ${i}`;
    exigir(Number.isInteger(m.f) && m.f >= 0 && m.f < fluxos.length, `${onde}: \`f\` não aponta para um fluxo`);
    exigir(Number.isFinite(m.t), `${onde}: falta \`t\``);
    exigir(i === 0 || m.t >= medicoes[i - 1].t, `${onde}: fora da ordem de \`t\``);
    exigir(classes.includes(m.atual) && classes.includes(m.previsto), `${onde}: classe fora de ${classes.join(", ")}`);
    exigir(m.timeout === 0 || m.timeout === 1, `${onde}: \`timeout\` deve ser 0 ou 1`);
    exigir(ehNumeroOuNulo(m.rtt) && m.rtt !== undefined, `${onde}: falta \`rtt\``);
    exigir(typeof m.conferivel === "boolean", `${onde}: falta \`conferivel\``);
    exigir(!m.conferivel || (classes.includes(m.futuro) && Number.isFinite(m.t_futuro)), `${onde}: conferível sem \`futuro\` ou \`t_futuro\``);
    exigir(Array.isArray(m.x) && m.x.length === colunas.length && m.x.every(ehNumeroOuNulo), `${onde}: \`x\` não tem ${colunas.length} valores`);
    exigir(Number.isInteger(m.folha) && typeof regras[m.folha] === "string", `${onde}: a folha ${m.folha} não tem regra`);
  });
}

// --- Busca no tempo ----------------------------------------------------------------------------------------

// Quantas medições já aconteceram no instante dado (as de `t` <= instante). As medições estão em ordem de `t`, então
// é uma busca binária pela primeira com `t` > instante; o resultado é o índice da próxima medição a acontecer.
function quantasAte(medicoes, instante) {
  let baixo = 0;
  let alto = medicoes.length;
  while (baixo < alto) {
    const meio = (baixo + alto) >> 1;
    if (medicoes[meio].t <= instante) {
      baixo = meio + 1;
    } else {
      alto = meio;
    }
  }
  return baixo;
}

// Para cada fluxo, os índices das suas medições (em ordem). Serve para achar a última medição de um fluxo até um ponto.
function indicesPorFluxo(medicoes, quantidadeDeFluxos) {
  const porFluxo = Array.from({ length: quantidadeDeFluxos }, () => []);
  medicoes.forEach((medicao, indice) => porFluxo[medicao.f].push(indice));
  return porFluxo;
}

// Posição, na lista de medições do fluxo `f`, da última medição que já aconteceu (as `tempo.proxima` primeiras); -1 se ainda
// não há. Busca binária na lista de índices do fluxo.
function posicaoDaUltimaDoFluxo(tempo, f) {
  const indices = tempo.indicesPorFluxo[f];
  let baixo = 0;
  let alto = indices.length;
  while (baixo < alto) {
    const meio = (baixo + alto) >> 1;
    if (indices[meio] < tempo.proxima) {
      baixo = meio + 1;
    } else {
      alto = meio;
    }
  }
  return baixo - 1;
}

// Índice (em `tempo.medicoes`) da última medição do fluxo `f` que já aconteceu; -1 se ainda não há.
function ultimaDoFluxo(tempo, f) {
  const posicao = posicaoDaUltimaDoFluxo(tempo, f);
  return posicao < 0 ? -1 : tempo.indicesPorFluxo[f][posicao];
}

// Índice da medição mais recente do fluxo `f` cuja previsão já foi conferida: conferível e com `t_futuro` <= o relógio
// (a mesma regra que o placar usa para contar uma conferência). -1 se o fluxo ainda não tem nenhuma. Anda para trás a
// partir da última medição que já aconteceu; as vizinhas dela quase nunca estão conferidas (o futuro delas ainda não
// chegou), então a busca para em poucos passos.
function ultimaConferidaDoFluxo(tempo, f) {
  const indices = tempo.indicesPorFluxo[f];
  for (let posicao = posicaoDaUltimaDoFluxo(tempo, f); posicao >= 0; posicao -= 1) {
    const medicao = tempo.medicoes[indices[posicao]];
    if (medicao.conferivel && medicao.t_futuro <= tempo.agora) {
      return indices[posicao];
    }
  }
  return -1;
}

// O intervalo típico entre duas medições seguidas do MESMO fluxo, em segundos (a mediana): serve para dimensionar o tempo
// do veredito no selo. Vem dos dados, não de uma constante; null se nenhum fluxo tem duas medições.
function intervaloTipicoDasMedicoes(medicoes, porFluxo) {
  const intervalos = [];
  for (const indices of porFluxo) {
    for (let k = 1; k < indices.length; k += 1) {
      intervalos.push(medicoes[indices[k]].t - medicoes[indices[k - 1]].t);
    }
  }
  intervalos.sort((a, b) => a - b);
  return intervalos.length === 0 ? null : intervalos[intervalos.length >> 1];
}

// As regiões de destino que aparecem nos fluxos, sem repetir, em ordem alfabética. Nada de lista fixa na página.
function regioesDosFluxos(fluxos) {
  return [...new Set(fluxos.map((fluxo) => fluxo.regiao))].sort((a, b) => a.localeCompare(b, "pt-BR"));
}

// --- Contadores --------------------------------------------------------------------------------------------

// Timeout = a medição marcou `timeout` ou veio sem RTT. Uma só regra, usada aqui e no mapa (pulso de timeout).
function ehTimeout(medicao) {
  return Boolean(medicao.timeout) || medicao.rtt === null;
}

function criarContadores(classes) {
  return { contagem: Object.fromEntries(classes.map((classe) => [classe, 0])), timeouts: 0, semFuturo: 0 };
}

// Soma uma medição que "aconteceu" nos contadores: classe do `status_atual`, timeouts e as sem futuro para conferir.
function somarMedicao(tempo, medicao) {
  tempo.contagem[medicao.atual] += 1;
  if (ehTimeout(medicao)) {
    tempo.timeouts += 1;
  }
  if (!medicao.conferivel) {
    tempo.semFuturo += 1;
  }
}

// --- O estado ----------------------------------------------------------------------------------------------

// Cria o estado no início do replay. Valida o JSON primeiro. `agora` e `proxima` partem do começo e andam juntos.
function criarTempo(replay) {
  validarReplay(replay);
  const { medicoes, fluxos } = replay;
  const classes = replay.meta.classes;
  const porFluxo = indicesPorFluxo(medicoes, fluxos.length);
  const conferencias = listarConferencias(medicoes); // as conferíveis, na ordem em que o relógio alcança o futuro delas
  // O relógio começa 1 s ANTES da primeira medição: assim o estado "nada aconteceu ainda" também é o estado de um
  // instante (e pular para o começo dá o mesmo que carregar a página). A primeira medição acontece 1 s depois.
  const inicio = medicoes[0].t - 1;
  const tempo = {
    medicoes,
    classes,
    conferencias,
    indicesPorFluxo: porFluxo,
    intervaloTipicoS: intervaloTipicoDasMedicoes(medicoes, porFluxo),
    inicio, // segundos UTC desde 1970, como o `t` de todas as medições
    fim: medicoes[medicoes.length - 1].t, // o relógio para aqui
    agora: inicio,
    proxima: 0, // índice da próxima medição a "acontecer"; as anteriores já aconteceram
    placar: null,
    ...criarContadores(classes),
  };
  irParaTempo(tempo, inicio);
  return tempo;
}

function terminou(tempo) {
  return tempo.proxima >= tempo.medicoes.length;
}

// Avança o relógio até `instante` (nunca além do fim) e devolve o que aconteceu nesse trecho, na ordem do JSON:
//   soltas: os índices das medições que aconteceram (o mapa solta um pulso para cada uma);
//   conferidas: as medições cujo futuro o relógio acabou de alcançar (o mapa mostra ✓ ou ✗ no selo).
function avancarTempo(tempo, instante) {
  tempo.agora = Math.min(instante, tempo.fim);
  const soltas = [];
  while (!terminou(tempo) && tempo.medicoes[tempo.proxima].t <= tempo.agora) {
    somarMedicao(tempo, tempo.medicoes[tempo.proxima]);
    soltas.push(tempo.proxima);
    tempo.proxima += 1;
  }
  // As conferências vêm DEPOIS das medições: no fim do replay as que estavam pendentes são contadas (o exportador
  // garante que todo `t_futuro` é <= o fim).
  const conferidas = conferirAte(tempo.placar, tempo.medicoes, tempo.conferencias, tempo.agora);
  return { soltas, conferidas };
}

// Põe o relógio em qualquer instante (antes ou depois do atual) e recalcula tudo do zero, sem tocar pulso nenhum:
// `proxima` por busca binária, contadores somando as medições até lá e o placar com `placarAte`.
function irParaTempo(tempo, instante) {
  tempo.agora = Math.min(Math.max(instante, tempo.inicio), tempo.fim);
  tempo.proxima = quantasAte(tempo.medicoes, tempo.agora);
  Object.assign(tempo, criarContadores(tempo.classes));
  for (let i = 0; i < tempo.proxima; i += 1) {
    somarMedicao(tempo, tempo.medicoes[i]);
  }
  tempo.placar = placarAte(tempo.classes, tempo.medicoes, tempo.conferencias, tempo.agora);
}

export { DICA_REPLAY, avancarTempo, criarTempo, ehTimeout, irParaTempo, regioesDosFluxos, terminou, ultimaConferidaDoFluxo, ultimaDoFluxo };
