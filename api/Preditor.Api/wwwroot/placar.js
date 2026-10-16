// placar.js: placar, matriz e feed de conferências do replay (SPEC-visualizacao.md, "Comportamento da página", itens 5 e 6).
//
// Lógica pura, sem DOM: pode ser rodada em Node sobre o `replay.json`. Aqui só se COMPARA e SOMA campos que já vêm no
// JSON (`previsto`, `atual`, `futuro`, `t_futuro`); nenhuma métrica do X nem rótulo é calculado.
//
// O placar é uma função do relógio: ele conta as medições conferíveis cujo `t_futuro` já passou (<= instante).
//   - `conferirAte` avança um placar já existente (o caminho do replay tocando, quadro a quadro);
//   - `placarAte` recalcula do zero até um instante qualquer (o caminho de pular no tempo, na V6).
// As duas usam a mesma soma (`somarConferencia`), então dão sempre o mesmo resultado.

// O que fazer quando o JSON é de uma versão antiga (sem `t_futuro`, por exemplo): o mesmo comando que o gera de novo.
const DICA_REPLAY = "Rode antes: uv run python -m preditor replay";

// As conferíveis em ordem de `t_futuro` (a ordem em que o relógio as alcança). O sort é estável: no mesmo instante,
// vale a ordem do JSON. Cada item guarda só o índice da medição e o instante, para não copiar as medições.
// Um `replay.json` sem `t_futuro` numérico numa medição conferível é de uma versão antiga: falha alto, em vez de
// ordenar por `undefined` e mostrar um placar errado sem aviso.
function listarConferencias(medicoes) {
  const lista = [];
  medicoes.forEach((medicao, indice) => {
    if (!medicao.conferivel) {
      return;
    }
    if (!Number.isFinite(medicao.t_futuro)) {
      throw new Error(`replay.json fora do formato: a medição ${indice} é conferível, mas não tem \`t_futuro\` (arquivo antigo?). ${DICA_REPLAY}`);
    }
    lista.push({ indice, tFuturo: medicao.t_futuro });
  });
  return lista.sort((a, b) => a.tFuturo - b.tFuturo);
}

// Placar zerado. `proxima` é quantas conferências já foram contadas (a posição na lista de `listarConferencias`).
function criarPlacar(classes) {
  return {
    classes,
    proxima: 0,
    conferidas: 0,
    acertosArvore: 0,
    acertosPersistencia: 0,
    // matriz[linha][coluna]: linha = classe verdadeira (`futuro`), coluna = classe prevista; ordem de `classes`.
    matriz: classes.map(() => classes.map(() => 0)),
  };
}

// A árvore acertou? `previsto` igual ao `futuro` da mesma medição.
function acertou(medicao) {
  return medicao.previsto === medicao.futuro;
}

// Soma uma conferência: árvore = `previsto` contra `futuro`; persistência = `atual` contra `futuro` ("o futuro é igual
// ao atual", RFC §9). Uma classe fora de `classes` é dado quebrado: lança erro em vez de contar errado.
function somarConferencia(placar, medicao) {
  const linha = placar.classes.indexOf(medicao.futuro);
  const coluna = placar.classes.indexOf(medicao.previsto);
  if (linha < 0 || coluna < 0) {
    throw new Error(`replay.json fora do formato: classe desconhecida (previsto ${medicao.previsto}, futuro ${medicao.futuro})`);
  }
  placar.conferidas += 1;
  placar.matriz[linha][coluna] += 1;
  if (acertou(medicao)) {
    placar.acertosArvore += 1;
  }
  if (medicao.atual === medicao.futuro) {
    placar.acertosPersistencia += 1;
  }
}

// Conta no placar todas as conferências com `t_futuro` <= instante que ainda não foram contadas. Só avança (o relógio
// do replay só anda para a frente); para voltar no tempo, use `placarAte`. Devolve as medições contadas agora, na ordem.
function conferirAte(placar, medicoes, conferencias, instante) {
  const novas = [];
  while (placar.proxima < conferencias.length && conferencias[placar.proxima].tFuturo <= instante) {
    const medicao = medicoes[conferencias[placar.proxima].indice];
    somarConferencia(placar, medicao);
    novas.push(medicao);
    placar.proxima += 1;
  }
  return novas;
}

// O placar como ele está no instante dado, calculado do zero (mesmo resultado de tocar desde o início até lá).
function placarAte(classes, medicoes, conferencias, instante) {
  const placar = criarPlacar(classes);
  conferirAte(placar, medicoes, conferencias, instante);
  return placar;
}

// As últimas `quantas` medições já conferidas no placar, a mais recente primeiro (o feed do painel). `aceita` filtra o
// que o feed mostra (só os erros, só as regiões ligadas): anda para trás na lista de conferências até juntar `quantas`
// que passem. O placar em si não é filtrado por isso: ele já foi somado inteiro.
function ultimasConferencias(placar, medicoes, conferencias, quantas, aceita = () => true) {
  const achadas = [];
  for (let i = placar.proxima - 1; i >= 0 && achadas.length < quantas; i -= 1) {
    const medicao = medicoes[conferencias[i].indice];
    if (aceita(medicao)) {
      achadas.push(medicao);
    }
  }
  return achadas;
}

export { DICA_REPLAY, acertou, listarConferencias, conferirAte, placarAte, ultimasConferencias };
