// rotas.js: tamanho do mapa, projeção e a geometria das rotas (SPEC-visualizacao.md).
//
// Só GEOMETRIA e preparo dos dados: nada aqui desenha. Usa o global `d3` (web/vendor/) para a projeção e o círculo máximo.
// Todas as coordenadas estão no sistema do mapa (LARGURA x ALTURA); o canvas e o SVG são escalados para caber na tela.

// --- Constantes do mapa ---------------------------------------------------------------------------------

// Tamanho do mapa em "unidades do mapa"; o SVG e o canvas usam o mesmo retângulo (o CSS o estica na tela).
const LARGURA = 960;
const ALTURA = 500;

// Rotação da projeção, em graus [longitude, latitude]. A projeção põe no centro a longitude -ROTACAO[0]: com 105 o
// centro do mapa fica em 105° O e o "corte" (a borda esquerda e direita, onde o mundo é aberto) cai na longitude
// oposta, 75° L. A rotação foi escolhida para esse corte cair onde nenhuma rota passa; com a rotação padrão ([0, 0])
// o corte ficaria no Pacífico, por onde passam os cabos para o Japão. Se as rotas ou o catálogo de cabos mudarem, a
// conferência do corte (`conferirCorte`) roda em todo carregamento e avisa na página e no console.
const ROTACAO = [105, 0];

// --- Constantes da rota ---------------------------------------------------------------------------------

// Raio médio da Terra: o mesmo de `RAIO_TERRA_KM` em config.py, para os km daqui baterem com os do JSON.
const RAIO_DA_TERRA_KM = 6371.0088;

// Cada trecho é amostrado de PASSO_KM em PASSO_KM pelo círculo máximo: assim a linha acompanha a curvatura do mapa
// (uma reta entre dois pontos da projeção não seria o caminho mais curto na esfera).
const PASSO_KM = 150;

// Os fluxos que compartilham um cabo ou um backbone caminham na mesma linha. Cada fluxo ganha um deslocamento
// lateral pequeno, em unidades do mapa, para os pulsos não ficarem exatamente empilhados: o fluxo de índice i usa a
// faixa (i mod FAIXAS_LATERAIS), de -(FAIXAS-1)/2 a +(FAIXAS-1)/2 vezes DESLOCAMENTO_LATERAL.
const FAIXAS_LATERAIS = 5;
const DESLOCAMENTO_LATERAL = 1.5; // banda total = 4 x 1,5 = 6 unidades: o pulso (raio 5) continua sobre a linha

// `deslocarLateralmente` olha, para cada lado de um vértice, até JANELA_DA_NORMAL unidades do mapa para achar a direção
// da linha; distâncias menores que DIRECAO_MINIMA não dão direção confiável e são ignoradas. Os dois valores foram
// escolhidos medindo as rotas do replay (nenhum segmento deslocado cresce mais que ~2 unidades); sem fonte externa.
const JANELA_DA_NORMAL = 8;
const DIRECAO_MINIMA = 1;

// Conferência do corte: dois pontos vizinhos da rota nunca ficam a mais que isto de distância na tela (em 150 km a
// distância é de poucas unidades); um salto maior é a linha atravessando o mapa de uma borda à outra.
const SALTO_MAXIMO = LARGURA / 4;

// Quando dois nós caem na mesma posição, fica o de maior prioridade (a sonda e o destino são os que importam).
const PRIORIDADE_DOS_NOS = { pop: 1, aterragem: 2, sonda: 3, destino: 4 };

// Espaço livre mínimo entre dois desenhos (rótulos, nós, grades de selos) para eles não contarem como "encostados".
const FOLGA_ENTRE_ROTULOS = 2; // em unidades do mapa

// --- Projeção e mapa-base --------------------------------------------------------------------------------

// Projeção plana (Natural Earth) ajustada para o mapa inteiro caber em LARGURA x ALTURA.
function criarProjecao() {
  return d3.geoNaturalEarth1().rotate(ROTACAO).fitSize([LARGURA, ALTURA], { type: "Sphere" });
}

// --- Geometria: caminhos amostrados pelo círculo máximo ----------------------------------------------------

// Distância em km entre dois pontos [lon, lat] pelo círculo máximo (d3.geoDistance devolve radianos).
function distanciaKm(de, ate) {
  return d3.geoDistance(de, ate) * RAIO_DA_TERRA_KM;
}

// Amostra uma polilinha [lon, lat] de PASSO_KM em PASSO_KM. Entre dois pontos consecutivos a posição vem do círculo
// máximo (d3.geoInterpolate) e só depois é projetada: assim a linha acompanha a curvatura do mapa.
// Devolve `pontos` (já em coordenadas do mapa) e `acumulado` (km percorridos até cada ponto, começando em 0).
function amostrarCaminho(caminho, projecao) {
  const pontos = [projecao(caminho[0])];
  const acumulado = [0];
  for (let i = 0; i + 1 < caminho.length; i += 1) {
    const de = caminho[i];
    const ate = caminho[i + 1];
    const km = distanciaKm(de, ate);
    const partes = Math.max(1, Math.ceil(km / PASSO_KM));
    const interpolar = d3.geoInterpolate(de, ate);
    const kmAnterior = acumulado[acumulado.length - 1];
    for (let parte = 1; parte <= partes; parte += 1) {
      pontos.push(projecao(interpolar(parte / partes)));
      acumulado.push(kmAnterior + (km * parte) / partes);
    }
  }
  return { pontos, acumulado };
}

// O ponto da amostra a `fracao` (0 a 1) do comprimento do caminho, medido em km.
function pontoNaFracao(amostra, fracao) {
  const total = amostra.acumulado[amostra.acumulado.length - 1];
  return amostra.pontos[indiceDoSegmento(amostra.acumulado, fracao * total)];
}

// Amostra a rota inteira: os caminhos dos trechos, um depois do outro. O primeiro ponto de cada trecho é o último do
// anterior (o exportador garante o encadeamento), então não é repetido.
function amostrarRota(trechos, projecao) {
  const pontos = [];
  const acumulado = [];
  for (const trecho of trechos) {
    const parte = amostrarCaminho(trecho.caminho, projecao);
    const primeiro = pontos.length === 0 ? 0 : 1;
    const kmAnterior = acumulado.length === 0 ? 0 : acumulado[acumulado.length - 1];
    for (let i = primeiro; i < parte.pontos.length; i += 1) {
      pontos.push(parte.pontos[i]);
      acumulado.push(kmAnterior + parte.acumulado[i]);
    }
  }
  return { pontos, acumulado };
}

// O vértice mais próximo que fica a pelo menos JANELA_DA_NORMAL de `i`, andando pela linha no `sentido` (-1 ou +1);
// se a linha acabar antes, o último vértice dela.
function vizinhoDistante(pontos, i, sentido) {
  let j = i;
  let percorrido = 0;
  while (percorrido < JANELA_DA_NORMAL && pontos[j + sentido] !== undefined) {
    percorrido += Math.hypot(pontos[j + sentido][0] - pontos[j][0], pontos[j + sentido][1] - pontos[j][1]);
    j += sentido;
  }
  return pontos[j];
}

// Vetor de comprimento 1 de `de` até `ate`; null se os pontos estão a menos de DIRECAO_MINIMA (direção instável).
function direcaoUnitaria(de, ate) {
  const dx = ate[0] - de[0];
  const dy = ate[1] - de[1];
  const comprimento = Math.hypot(dx, dy);
  return comprimento < DIRECAO_MINIMA ? null : [dx / comprimento, dy / comprimento];
}

// Empurra cada ponto para o lado, na perpendicular da linha naquele ponto. Por que não é só "perpendicular ao vizinho
// de antes e ao de depois": segmentos de poucos km (a sonda colada no ponto de troca, o backbone de 4 km) ganhavam,
// nas duas pontas, direções de segmentos longos bem diferentes, e o segmento curto virava um salto de lado. Aqui:
//   1. a direção chegando e a saindo do vértice vêm de vizinhos a pelo menos JANELA_DA_NORMAL de distância, então
//      vértices vizinhos enxergam quase a mesma direção;
//   2. o deslocamento vale perpendicular(chegando + saindo) * deslocamento / 2: numa reta é o deslocamento inteiro e
//      numa curva fechada ele encolhe (cos do meio-ângulo), em vez de esticar os segmentos ao redor da curva.
function deslocarLateralmente(pontos, deslocamento) {
  return pontos.map((ponto, i) => {
    const chegando = direcaoUnitaria(vizinhoDistante(pontos, i, -1), ponto);
    const saindo = direcaoUnitaria(ponto, vizinhoDistante(pontos, i, 1));
    // Nas pontas da rota (ou perto delas) uma das direções não existe: usa a outra. Sem nenhuma, não desloca.
    const [ax, ay] = chegando ?? saindo ?? [0, 0];
    const [bx, by] = saindo ?? chegando ?? [0, 0];
    return [ponto[0] - ((ay + by) * deslocamento) / 2, ponto[1] + ((ax + bx) * deslocamento) / 2];
  });
}

// Faixa lateral do fluxo de índice `indice`: de -(FAIXAS-1)/2 a +(FAIXAS-1)/2 vezes DESLOCAMENTO_LATERAL.
function deslocamentoDoFluxo(indice) {
  return ((indice % FAIXAS_LATERAIS) - (FAIXAS_LATERAIS - 1) / 2) * DESLOCAMENTO_LATERAL;
}

// Índice i do ponto em que começa o segmento que contém `km` (acumulado[i] <= km < acumulado[i + 1]); busca binária.
function indiceDoSegmento(acumulado, km) {
  let baixo = 0;
  let alto = acumulado.length - 2; // o último segmento começa no penúltimo ponto
  while (baixo < alto) {
    const meio = Math.ceil((baixo + alto) / 2);
    if (acumulado[meio] <= km) {
      baixo = meio;
    } else {
      alto = meio - 1;
    }
  }
  return baixo;
}

// --- Rota de um fluxo -----------------------------------------------------------------------------------
//
// A rota é a lista de trechos do JSON (terrestres e submarinos), amostrada pelo círculo máximo. Quem usa a rota só
// chama `rota.posicaoEm(u)` e `rota.pontosEntre(u0, u1)`, com u de 0 (sonda) a 1 (destino) medido em KM reais ao
// longo da rota inteira: o pulso anda na mesma velocidade (em km por segundo) em todos os trechos.
function criarRota(fluxo, projecao, indice) {
  const amostra = amostrarRota(fluxo.trechos, projecao);
  const pontos = deslocarLateralmente(amostra.pontos, deslocamentoDoFluxo(indice));
  const acumulado = amostra.acumulado;
  const total = acumulado[acumulado.length - 1];

  function kmEm(u) {
    return Math.min(Math.max(u, 0), 1) * total;
  }

  function posicaoEm(u) {
    const km = kmEm(u);
    const i = indiceDoSegmento(acumulado, km);
    const comprimento = acumulado[i + 1] - acumulado[i];
    const t = comprimento > 0 ? (km - acumulado[i]) / comprimento : 0;
    const [x0, y0] = pontos[i];
    const [x1, y1] = pontos[i + 1];
    return [x0 + (x1 - x0) * t, y0 + (y1 - y0) * t];
  }

  // Os pontos do trecho [u0, u1] da rota: as duas pontas e todos os vértices no meio, para o rastro fazer as curvas.
  function pontosEntre(u0, u1) {
    const primeiro = indiceDoSegmento(acumulado, kmEm(u0)) + 1;
    const ultimo = indiceDoSegmento(acumulado, kmEm(u1));
    return [posicaoEm(u0), ...pontos.slice(primeiro, ultimo + 1), posicaoEm(u1)];
  }

  return { pontos, posicaoEm, pontosEntre };
}

// Uma rota por fluxo, na mesma ordem de `fluxos` (o `f` de cada medição é a posição nessa lista).
function criarRotas(fluxos, projecao) {
  return fluxos.map((fluxo, indice) => criarRota(fluxo, projecao, indice));
}

// Conferência do corte da projeção (o app.js a chama em todo carregamento): conta os pares de pontos vizinhos das
// rotas que ficam longe demais na tela, o sinal de uma linha atravessando o mapa por causa da borda.
function conferirCorte(rotas) {
  let pares = 0;
  let saltos = 0;
  for (const rota of rotas) {
    for (let i = 0; i + 1 < rota.pontos.length; i += 1) {
      pares += 1;
      const [x0, y0] = rota.pontos[i];
      const [x1, y1] = rota.pontos[i + 1];
      if (Math.hypot(x1 - x0, y1 - y0) > SALTO_MAXIMO) {
        saltos += 1;
      }
    }
  }
  return { rotas: rotas.length, pares, saltos };
}

// --- Trechos e nós desenhados (cada um uma vez só) ------------------------------------------------------

function chaveDoPonto(ponto) {
  return `${ponto[0]},${ponto[1]}`;
}

// Os pares de pontos consecutivos do trecho, sem importar o sentido (A→B é o mesmo que B→A): a chave de cada par e o
// km dele (círculo máximo, como o exportador).
function paresDoTrecho(trecho) {
  const pares = [];
  for (let i = 0; i + 1 < trecho.caminho.length; i += 1) {
    const de = trecho.caminho[i];
    const ate = trecho.caminho[i + 1];
    const ordenados = [chaveDoPonto(de), chaveDoPonto(ate)].sort();
    pares.push({ chave: `${trecho.tipo}|${trecho.nome}|${ordenados.join("|")}`, km: distanciaKm(de, ate) });
  }
  return pares;
}

// Os trechos a desenhar. Dezenas de fluxos repetem o mesmo cabo ou backbone, então:
//   1. trechos idênticos (mesmo tipo, nome e caminho) viram um só;
//   2. os mais longos vêm primeiro, e um trecho cujos pares de pontos já foram todos desenhados é pulado (é o caso
//      de um cabo que um fluxo usa inteiro e outro usa só a ponta).
// Cada trecho desenhado leva `kmDoCartao`, o número que o cartão pode mostrar sem enganar quem aponta para a linha:
//   - cabo submarino: o comprimento do cabo inteiro desenhado (união dos pares de todos os trechos daquele cabo);
//   - trecho terrestre: o km do trecho, só se nenhum outro trecho passa pelos mesmos pares; sobreposto, é null
//     (a linha desenhada serve a vários fluxos e nenhum km seria o do que está sob o cursor).
// E `usuarios`, o conjunto de fluxos (índices) que passam por algum par do trecho desenhado, inclusive os que usam só
// um pedaço dele: o filtro por região esconde a linha só quando nenhum fluxo visível a usa.
function trechosDistintos(fluxos) {
  const unicos = new Map();
  for (const fluxo of fluxos) {
    for (const trecho of fluxo.trechos) {
      unicos.set(`${trecho.tipo}|${trecho.nome}|${JSON.stringify(trecho.caminho)}`, trecho);
    }
  }
  const maioresPrimeiro = [...unicos.values()].sort((a, b) => b.km - a.km);

  // Quantos trechos distintos usam cada par, e os pares (com km) de cada cabo, sem repetir par.
  const usosDoPar = new Map();
  const paresDoCabo = new Map();
  const paresPorTrecho = new Map();
  for (const trecho of maioresPrimeiro) {
    const pares = paresDoTrecho(trecho);
    paresPorTrecho.set(trecho, pares);
    for (const par of pares) {
      usosDoPar.set(par.chave, (usosDoPar.get(par.chave) ?? 0) + 1);
      if (trecho.tipo === "submarino") {
        paresDoCabo.set(trecho.nome, (paresDoCabo.get(trecho.nome) ?? new Map()).set(par.chave, par.km));
      }
    }
  }

  // Quais fluxos usam cada par de pontos (todos os trechos de todos os fluxos, antes de juntar os repetidos).
  const fluxosDoPar = new Map();
  fluxos.forEach((fluxo, f) => {
    for (const trecho of fluxo.trechos) {
      for (const par of paresDoTrecho(trecho)) {
        fluxosDoPar.set(par.chave, (fluxosDoPar.get(par.chave) ?? new Set()).add(f));
      }
    }
  });

  const paresDesenhados = new Set();
  const desenhar = [];
  for (const trecho of maioresPrimeiro) {
    const pares = paresPorTrecho.get(trecho);
    if (pares.every((par) => paresDesenhados.has(par.chave))) {
      continue;
    }
    pares.forEach((par) => paresDesenhados.add(par.chave));
    let kmDoCartao = null;
    if (trecho.tipo === "submarino") {
      kmDoCartao = [...paresDoCabo.get(trecho.nome).values()].reduce((soma, km) => soma + km, 0);
    } else if (pares.every((par) => usosDoPar.get(par.chave) === 1)) {
      kmDoCartao = trecho.km;
    }
    const usuarios = new Set(pares.flatMap((par) => [...fluxosDoPar.get(par.chave)]));
    desenhar.push({ ...trecho, kmDoCartao, usuarios });
  }
  return desenhar;
}

// A cidade do nome do nó de destino: o exportador o escreve como "Cidade (dst_addr)".
function cidadeDoDestino(nome) {
  return nome.split(" (")[0];
}

// Os nós a desenhar: um por posição. Se dois tipos caem no mesmo ponto, fica o de maior prioridade. O destino leva
// a cidade e o código do país do fluxo (o JSON não tem o país dentro do nó). `usuarios` = os fluxos (índices) que
// passam pelo ponto, de qualquer tipo, para o filtro por região. A lista sai com os de maior prioridade por último,
// para ficarem desenhados por cima.
function nosDistintos(fluxos) {
  const nos = new Map();
  fluxos.forEach((fluxo, f) => {
    for (const trecho of fluxo.trechos) {
      for (const no of trecho.nos) {
        const chave = chaveDoPonto(no.ponto);
        const atual = nos.get(chave) ?? { tipo: null, usuarios: new Set() };
        atual.usuarios.add(f);
        if (atual.tipo === null || PRIORIDADE_DOS_NOS[no.tipo] > PRIORIDADE_DOS_NOS[atual.tipo]) {
          const destino = no.tipo === "destino";
          Object.assign(atual, {
            tipo: no.tipo,
            nome: no.nome,
            ponto: no.ponto,
            cidade: destino ? cidadeDoDestino(no.nome) : null,
            pais: destino ? fluxo.pais : null,
          });
        }
        nos.set(chave, atual);
      }
    }
  });
  return [...nos.values()].sort((a, b) => PRIORIDADE_DOS_NOS[a.tipo] - PRIORIDADE_DOS_NOS[b.tipo]);
}

// "M x y L x y ..." de uma lista de pontos do mapa.
function textoDoCaminho(pontos) {
  return pontos.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
}

// Caixas (x, y, largura, altura, em unidades do mapa): duas encostam se estão a menos de FOLGA_ENTRE_ROTULOS uma da outra.
function encostam(a, b) {
  return (
    a.x < b.x + b.largura + FOLGA_ENTRE_ROTULOS &&
    b.x < a.x + a.largura + FOLGA_ENTRE_ROTULOS &&
    a.y < b.y + b.altura + FOLGA_ENTRE_ROTULOS &&
    b.y < a.y + a.altura + FOLGA_ENTRE_ROTULOS
  );
}

function cabeNoMapa(caixa) {
  return caixa.x >= 0 && caixa.y >= 0 && caixa.x + caixa.largura <= LARGURA && caixa.y + caixa.altura <= ALTURA;
}

// O ponto [lon, lat] do destino de um fluxo: o último nó do último trecho.
function destinoDoFluxo(fluxo) {
  const ultimoTrecho = fluxo.trechos[fluxo.trechos.length - 1];
  return ultimoTrecho.nos[ultimoTrecho.nos.length - 1].ponto;
}

export {
  ALTURA,
  LARGURA,
  amostrarCaminho,
  cabeNoMapa,
  chaveDoPonto,
  conferirCorte,
  criarProjecao,
  criarRotas,
  destinoDoFluxo,
  encostam,
  nosDistintos,
  pontoNaFracao,
  textoDoCaminho,
  trechosDistintos,
};
