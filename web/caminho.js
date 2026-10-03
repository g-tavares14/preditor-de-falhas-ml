// caminho.js: o caminho raiz → folha de uma medição na árvore (SPEC-arvore-na-pagina.md).
//
// Lógica pura, sem DOM: roda em Node sobre o `replay.json`. A página NÃO percorre a árvore com o X (isso seria prever):
// recebe a folha pronta do JSON e sobe pelos pais até a raiz. O lado tomado em cada divisão vem do próximo nó do
// caminho, não de uma comparação. O `replay` em Python confere que descer pelos nós com o `x` do JSON chega na mesma folha.

// Ids dos nós da raiz até `folha`, subindo por `pai`.
function caminhoAteFolha(nos, folha) {
  const ids = [];
  for (let no = nos[folha]; no !== undefined; no = no.pai === null ? undefined : nos[no.pai]) {
    ids.push(no.id);
  }
  return ids.reverse();
}

// Um passo por divisão do caminho: a coluna, o limiar, o valor que a medição tinha (null = ausente) e o lado tomado.
// `valores` = nome da coluna → valor (como veio no JSON).
function passosDoCaminho(nos, folha, valores) {
  const ids = caminhoAteFolha(nos, folha);
  return ids.slice(0, -1).map((id, i) => {
    const no = nos[id];
    const foiEsquerda = ids[i + 1] === no.esquerda; // esquerda = "coluna ≤ limiar" (convenção do scikit-learn)
    return { id, coluna: no.coluna, limiar: no.limiar, valor: valores[no.coluna], foiEsquerda, ausente: no.ausente };
  });
}

// Nome da coluna → valor, para a árvore escolhida: a oficial lê `x`; a ajustada, `x` e `x_ajuste`.
function valoresDaMedicao(medicao, colunasOficiais, colunasAjuste) {
  const valores = {};
  colunasOficiais.forEach((coluna, i) => (valores[coluna] = medicao.x[i]));
  colunasAjuste.forEach((coluna, i) => (valores[coluna] = medicao.x_ajuste[i]));
  return valores;
}

export { caminhoAteFolha, passosDoCaminho, valoresDaMedicao };
