// foco.js: "roving tabindex" para um grupo de elementos do mapa (SPEC-visualizacao.md, V7: teclado e foco).
//
// O mapa tem 79 selos de previsão e 7 cabos que recebem foco. Se todos estivessem na ordem do Tab, chegar aos controles
// do relógio custaria dezenas de teclas. Aqui o grupo inteiro vira UMA parada do Tab: só o elemento "atual" tem
// tabindex 0 (os outros, -1) e as setas movem o foco de um para o outro. É o padrão de listas, barras de ferramentas e
// grades da WAI-ARIA. Quem sai do grupo com Tab e volta cai de novo no último elemento em que estava.

// Para onde uma tecla leva: a posição seguinte ou anterior (as setas), a primeira ou a última (Home e End); null se a
// tecla não é de navegação ou se não há para onde ir (nas pontas o foco fica onde está: sem dar a volta).
function posicaoDaTecla(tecla, posicao, quantidade) {
  const destinos = {
    ArrowRight: posicao + 1,
    ArrowDown: posicao + 1,
    ArrowLeft: posicao - 1,
    ArrowUp: posicao - 1,
    Home: 0,
    End: quantidade - 1,
  };
  const destino = destinos[tecla];
  return destino === undefined || destino < 0 || destino >= quantidade || destino === posicao ? null : destino;
}

// `itens`: os elementos do DOM do grupo, na ordem das setas (a mesma ordem em que foram criados). Um elemento com a classe
// `oculto` (filtro por região) não conta: não recebe foco e não vira o "atual". Devolve `conferir`: deve ser chamada
// sempre que algum item é escondido ou mostrado, para o grupo nunca ficar sem parada no Tab.
function criarGrupoDeFoco(itens) {
  let atual = null;

  const visiveis = () => itens.filter((item) => !item.classList.contains("oculto"));

  function definirAtual(item) {
    atual = item;
    itens.forEach((outro) => outro.setAttribute("tabindex", outro === item ? "0" : "-1"));
  }

  // Se o "atual" sumiu (região desligada), o primeiro visível assume; sem nenhum visível, ninguém está no Tab.
  function conferir() {
    const lista = visiveis();
    if (atual === null || !lista.includes(atual)) {
      definirAtual(lista.length > 0 ? lista[0] : null);
    }
  }

  for (const item of itens) {
    // Quem recebe foco (Tab, setas ou clique) passa a ser o "atual".
    item.addEventListener("focus", () => definirAtual(item));
    item.addEventListener("keydown", (evento) => {
      const lista = visiveis();
      const destino = posicaoDaTecla(evento.key, lista.indexOf(item), lista.length);
      if (destino !== null && !evento.altKey && !evento.ctrlKey && !evento.metaKey) {
        evento.preventDefault(); // as setas não rolam a página
        lista[destino].focus();
      }
    });
  }

  conferir();
  return { conferir };
}

export { criarGrupoDeFoco };
