// arvore.js: o painel da árvore de decisão (SPEC-arvore-na-pagina.md).
//
// Desenha os 31 nós da árvore escolhida (oficial ou ajustada) em camadas e, com um fluxo em foco, acende o caminho que
// a última medição dele percorreu, com o valor de cada coluna ao lado do limiar. Nada é calculado: a folha, a classe e a
// regra vêm do JSON (caminho.js só sobe pelos pais). Só textContent e createElementNS, nunca innerHTML.

import { criarCelula, criarChip, formatarInstante } from "./comum.js";
import { passosDoCaminho, valoresDaMedicao } from "./caminho.js";
import { ultimaDoFluxo } from "./tempo.js";

const SVG = "http://www.w3.org/2000/svg";

// Medidas do desenho (unidades do viewBox; o SVG escala com a largura do cartão).
const LARGURA = 1280; // 16 folhas a 80 de distância
const ALTURA_DO_NIVEL = 62; // distância vertical entre camadas
const MARGEM_TOPO = 18;
const LARGURA_DO_NO = 74; // caixa de uma divisão (cabe "jitter_relativo" a 10 px)
const ALTURA_DO_NO = 30;
const LARGURA_DA_FOLHA = 48;
const ALTURA_DA_FOLHA = 30;

const NOMES = { oficial: "Oficial (Tarefa 3)", ajustada: "Ajustada (Tarefa 4)" };

// Número com vírgula, sem separador de milhar (como no cartão do fluxo).
function numero(valor, casas = 4) {
  return valor.toLocaleString("pt-BR", { maximumFractionDigits: casas, useGrouping: false });
}

function elementoSvg(tag, atributos, texto) {
  const el = document.createElementNS(SVG, tag);
  for (const [nome, valor] of Object.entries(atributos)) {
    el.setAttribute(nome, valor);
  }
  if (texto !== undefined) {
    el.textContent = texto;
  }
  return el;
}

// Posição de cada nó: as folhas, da esquerda para a direita, em colunas iguais; cada divisão no meio dos filhos.
function posicoes(nos) {
  const pos = new Array(nos.length);
  let proximaFolha = 0;
  const folhas = nos.filter((no) => no.coluna === null).length;
  const passo = LARGURA / folhas;
  function visitar(id, nivel) {
    const no = nos[id];
    const y = MARGEM_TOPO + nivel * ALTURA_DO_NIVEL;
    if (no.coluna === null) {
      pos[id] = { x: passo * (proximaFolha + 0.5), y };
      proximaFolha += 1;
    } else {
      visitar(no.esquerda, nivel + 1);
      visitar(no.direita, nivel + 1);
      pos[id] = { x: (pos[no.esquerda].x + pos[no.direita].x) / 2, y };
    }
  }
  visitar(0, 0);
  const niveis = Math.max(...pos.map((p) => p.y));
  return { pos, altura: niveis + ALTURA_DA_FOLHA + 22 };
}

// Desenha uma árvore inteira no SVG e devolve os elementos de cada nó e aresta, para acender o caminho depois.
function desenharArvore(svg, arvore) {
  const { nos } = arvore;
  const { pos, altura } = posicoes(nos);
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${LARGURA} ${altura}`);
  const arestas = elementoSvg("g", { class: "arv-arestas" });
  const caixas = elementoSvg("g", { class: "arv-nos" });
  const valores = elementoSvg("g", { class: "arv-valores" });
  svg.append(arestas, caixas, valores);

  const partes = { aresta: {}, no: {}, valor: {} };
  for (const no of nos) {
    const { x, y } = pos[no.id];
    if (no.pai !== null) {
      const p = pos[no.pai];
      const lado = nos[no.pai].esquerda === no.id ? "sim" : "não";
      const linha = elementoSvg("path", { d: `M${p.x},${p.y + ALTURA_DO_NO / 2} L${x},${y - ALTURA_DO_NO / 2}`, class: "arv-aresta" });
      arestas.append(linha);
      // "sim" / "não" no meio da aresta: esquerda = a condição do nó pai é verdadeira.
      arestas.append(elementoSvg("text", { x: (p.x + x) / 2 + (lado === "sim" ? -6 : 6), y: (p.y + y) / 2 + 4, class: "arv-lado", "text-anchor": lado === "sim" ? "end" : "start" }, lado));
      partes.aresta[no.id] = linha;
    }
    const grupo = elementoSvg("g", { class: "arv-no", transform: `translate(${x},${y})` });
    const total = no.n.reduce((a, b) => a + b, 0);
    if (no.coluna === null) {
      grupo.classList.add("arv-folha", `arv-${no.classe.toLowerCase()}`);
      grupo.append(
        elementoSvg("rect", { x: -LARGURA_DA_FOLHA / 2, y: -ALTURA_DA_FOLHA / 2, width: LARGURA_DA_FOLHA, height: ALTURA_DA_FOLHA }),
        elementoSvg("text", { y: -2, "text-anchor": "middle", class: "arv-classe" }, no.classe),
        elementoSvg("text", { y: 10, "text-anchor": "middle", class: "arv-n" }, `n ${total}`),
      );
      grupo.append(elementoSvg("title", {}, `Folha ${no.id}: ${no.classe}. No treino: ${no.n.join(" / ")} (OK / RISCO / FALHA).`));
    } else {
      grupo.append(
        elementoSvg("rect", { x: -LARGURA_DO_NO / 2, y: -ALTURA_DO_NO / 2, width: LARGURA_DO_NO, height: ALTURA_DO_NO }),
        elementoSvg("text", { y: -3, "text-anchor": "middle", class: "arv-coluna" }, no.coluna),
        elementoSvg("text", { y: 10, "text-anchor": "middle", class: "arv-limiar" }, `≤ ${numero(no.limiar)}`),
      );
      grupo.append(elementoSvg("title", {}, `${no.coluna} ≤ ${numero(no.limiar, 6)} (ausente vai para a ${no.ausente}). No treino: ${total} medições.`));
      // Valor da medição em foco: escrito acima da caixa só quando o nó está no caminho.
      const valor = elementoSvg("text", { x, y: y - ALTURA_DO_NO / 2 - 4, "text-anchor": "middle", class: "arv-valor" }, "");
      valores.append(valor);
      partes.valor[no.id] = valor;
    }
    caixas.append(grupo);
    partes.no[no.id] = grupo;
  }
  return partes;
}

// Monta o painel: o seletor das duas árvores e o primeiro desenho. Devolve o que `atualizarArvore` precisa.
function montarArvore(elementos, replay, aoTrocar) {
  const arvores = replay.arvores;
  const seletor = elementos.seletor;
  for (const chave of Object.keys(arvores)) {
    const rotulo = document.createElement("label");
    rotulo.className = "arv-opcao";
    const entrada = document.createElement("input");
    entrada.type = "radio";
    entrada.name = "arvore-escolhida";
    entrada.value = chave;
    entrada.checked = chave === "oficial";
    entrada.addEventListener("change", () => aoTrocar(chave));
    rotulo.append(entrada, ` ${NOMES[chave] ?? chave}`);
    seletor.append(rotulo);
  }
  return { chave: null, desenhada: null, partes: null, acesos: [] };
}

function apagarCaminho(painel) {
  for (const el of painel.acesos) {
    el.classList.remove("arv-aceso");
    if (el.tagName === "text") {
      el.textContent = "";
    }
  }
  painel.acesos = [];
}

// Texto de um passo: "z_robusto = 1,37 ≤ 2,0158 → sim" ou "jitter_relativo ausente → direita".
function textoDoPasso(passo) {
  if (passo.valor === null) {
    return `${passo.coluna} ausente → ${passo.ausente} (${passo.foiEsquerda ? "sim" : "não"})`;
  }
  const sinal = passo.foiEsquerda ? "≤" : ">";
  return `${passo.coluna} = ${numero(passo.valor)} ${sinal} ${numero(passo.limiar)} → ${passo.foiEsquerda ? "sim" : "não"}`;
}

// Acompanha o relógio: redesenha só quando muda a árvore escolhida, o fluxo em foco ou a medição dele.
function atualizarArvore(estado, elementos, painel) {
  const escolha = estado.arvoreEscolhida;
  const arvore = estado.arvores[escolha];
  if (painel.desenhada !== escolha) {
    painel.partes = desenharArvore(elementos.svg, arvore);
    painel.desenhada = escolha;
    painel.acesos = [];
    painel.chave = null;
    elementos.svg.setAttribute("aria-label", `Diagrama da árvore ${NOMES[escolha] ?? escolha}: ${arvore.nos.length} nós`);
  }
  const f = estado.selecionado;
  const indice = f === null ? -1 : ultimaDoFluxo(estado.tempo, f);
  const chave = `${escolha}|${f}|${indice}`;
  if (chave === painel.chave) {
    return;
  }
  painel.chave = chave;
  apagarCaminho(painel);
  if (indice < 0) {
    elementos.situacao.textContent = f === null
      ? "Selecione um fluxo (no mapa, no feed ou na lista) para ver o caminho da última medição dele."
      : "Este fluxo ainda não tem medição neste instante.";
    elementos.passos.replaceChildren();
    elementos.regra.textContent = "";
    return;
  }

  const medicao = estado.tempo.medicoes[indice];
  const ajustada = escolha === "ajustada";
  const folha = ajustada ? medicao.folha_ajustada : medicao.folha;
  const previsto = ajustada ? medicao.previsto_ajustada : medicao.previsto;
  const valores = valoresDaMedicao(medicao, estado.colunas, estado.colunasAjuste);
  const passos = passosDoCaminho(arvore.nos, folha, valores);

  // Acende nós, arestas e valores do caminho.
  const { partes } = painel;
  for (const passo of passos) {
    partes.no[passo.id].classList.add("arv-aceso");
    partes.valor[passo.id].textContent = passo.valor === null ? "ausente" : numero(passo.valor, 2);
    painel.acesos.push(partes.no[passo.id], partes.valor[passo.id]);
  }
  partes.no[folha].classList.add("arv-aceso");
  painel.acesos.push(partes.no[folha]);
  for (const passo of passos.slice(1).map((p) => p.id).concat(folha)) {
    partes.aresta[passo].classList.add("arv-aceso");
    painel.acesos.push(partes.aresta[passo]);
  }

  // O mesmo caminho em texto (leitor de tela e quem não distingue a cor do destaque).
  elementos.situacao.replaceChildren(
    `${estado.rotulos[f]} · ${formatarInstante(medicao.t).hora} UTC · folha ${folha} · previsão p/ 12 min `,
    criarChip(previsto),
  );
  elementos.passos.replaceChildren(...passos.map((passo) => criarCelula("li", textoDoPasso(passo))));
  elementos.regra.textContent = arvore.regras[folha].replaceAll("`", "");
}

export { atualizarArvore, montarArvore };
