// cartao.js: o cartão do fluxo selecionado (SPEC-visualizacao.md, "Comportamento da página", item 6, último ponto).
//
// Mostra a rota do fluxo, a última medição dele até o instante do relógio, as 8 colunas do X e a regra da folha que
// decidiu. Só escreve com textContent. Não calcula métrica: o X, a folha e a regra já vêm no JSON.

import { acertou } from "./placar.js";
import { ehTimeout, ultimaConferidaDoFluxo, ultimaDoFluxo } from "./tempo.js";
import { TEXTO_ACERTOU, TEXTO_ERROU, criarCelula, criarChip, detalhesDoFluxo, formatarInstante } from "./comum.js";

const TEXTO_AUSENTE = "ausente"; // valor de X sem número (o JSON o grava como null; nunca vira 0)
const SEM_FUTURO = "sem futuro para conferir";
const SEM_CONFERIDA = "nenhuma previsão conferida ainda";

// Cria as 8 linhas "coluna / valor" do X, com os nomes que vêm do JSON (`colunas`): a página não tem nome nenhum escrito.
function montarColunasDoCartao(lista, colunas) {
  return colunas.map((nome) => {
    const grupo = document.createElement("div");
    const valor = criarCelula("dd", "");
    const rotulo = criarCelula("dt", nome);
    rotulo.title = nome; // o nome inteiro, se a coluna estreita o cortar com reticências
    grupo.append(rotulo, valor);
    lista.append(grupo);
    return valor;
  });
}

// "123,5 ms" ou "timeout" (a medição sem nenhuma resposta).
function textoDoRtt(medicao) {
  return ehTimeout(medicao) ? "timeout" : `${medicao.rtt.toLocaleString("pt-BR", { maximumFractionDigits: 1, useGrouping: false })} ms`;
}

// Um valor de X: o número como veio (até 4 casas, vírgula, sem separador de milhar) ou "ausente", nunca 0.
function textoDoValorX(valor) {
  return valor === null ? TEXTO_AUSENTE : valor.toLocaleString("pt-BR", { maximumFractionDigits: 4, useGrouping: false });
}

// Situação da previsão da ÚLTIMA medição do fluxo. O cartão não adianta o futuro: o `futuro` dela só aparece na linha
// "última previsão conferida" (abaixo), depois que o relógio passa do `t_futuro`. A última medição que já aconteceu sempre
// tem o futuro adiante (ele é a 3ª medição seguinte, que ainda não aconteceu), então aqui só há "aguardando" ou "sem futuro".
function escreverSituacao(destino, medicao) {
  if (medicao === null) {
    destino.textContent = "ainda sem medição neste instante";
  } else if (!medicao.conferivel) {
    destino.textContent = SEM_FUTURO;
  } else {
    destino.textContent = `aguardando (confere às ${formatarInstante(medicao.t_futuro).hora})`;
  }
}

// A previsão mais recente do fluxo que o relógio já conferiu: a hora (UTC) em que foi feita, o que a árvore previu, o que
// aconteceu e o resultado (✓ ACERTOU ou ✗ ERROU, com texto e símbolo: nunca só cor). `medicao` é null se não há nenhuma.
function escreverConferida(campos, medicao) {
  campos.conferida.classList.remove("fluxo-acertou", "fluxo-errou");
  if (medicao === null) {
    campos.conferida.textContent = SEM_CONFERIDA;
    return;
  }
  const ok = acertou(medicao);
  campos.conferida.classList.add(ok ? "fluxo-acertou" : "fluxo-errou");
  const hora = criarCelula("span", `${formatarInstante(medicao.t).hora} `, "numero"); // quando a previsão foi feita (UTC)
  campos.conferida.replaceChildren(hora, criarChip(medicao.previsto), " → ", criarChip(medicao.futuro), ` ${ok ? "✓" : "✗"} ${ok ? TEXTO_ACERTOU : TEXTO_ERROU}`);
}

// A regra vem do `.txt` oficial da árvore, em Markdown, com os nomes das colunas entre crases (acentos graves); na página
// elas só atrapalham, então saem (só aqui: o JSON e o `.txt` ficam como estão).
function textoDaRegra(regra) {
  return regra.replaceAll("`", "");
}

// A parte do cartão que só muda quando se escolhe outro fluxo: a rota (sonda, destino, cabos, km) e os RTTs de referência.
function escreverRotaDoCartao(campos, fluxo) {
  const { sonda, cidade } = detalhesDoFluxo(fluxo);
  const trechos = fluxo.trechos.map((trecho) => trecho.nome).join(" → ");
  campos.titulo.textContent = `Sonda ${sonda} → ${cidade}, ${fluxo.pais}`;
  campos.opcao.textContent = fluxo.opcao;
  campos.trechos.textContent = trechos;
  campos.trechos.title = trechos;
  // Sem separador de milhar ("19.833" seria lido como decimal), como no cartão do trecho.
  campos.km.textContent = `${Math.round(fluxo.km)} km`;
  const minimo = `${fluxo.rtt_minimo_ms.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ms`;
  const mediana = fluxo.mediana_ms === null ? "sem baseline" : `${fluxo.mediana_ms.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ms`;
  campos.rtt.textContent = `mínimo ${minimo} × mediana ${mediana}`;
}

// A parte do cartão que acompanha o relógio: a última medição do fluxo, a última previsão conferida, o que a árvore viu e
// a regra da folha. `conferida` é a medição da última previsão já conferida do fluxo, ou null.
function escreverMedicaoDoCartao(estado, campos, valoresDeX, medicao, conferida) {
  const semMedicao = medicao === null;
  campos.hora.textContent = semMedicao ? "--" : `${formatarInstante(medicao.t).hora} UTC`;
  campos.rttAtual.textContent = semMedicao ? "--" : textoDoRtt(medicao);
  campos.atual.replaceChildren(...(semMedicao ? ["--"] : [criarChip(medicao.atual)]));
  campos.previsto.replaceChildren(...(semMedicao ? ["--"] : [criarChip(medicao.previsto)]));
  escreverSituacao(campos.situacao, medicao);
  escreverConferida(campos, conferida);
  valoresDeX.forEach((valor, i) => {
    valor.textContent = semMedicao ? "--" : textoDoValorX(medicao.x[i]);
    valor.classList.toggle("ausente", !semMedicao && medicao.x[i] === null);
  });
  campos.folha.textContent = semMedicao ? "" : `folha ${medicao.folha}`;
  campos.regra.textContent = semMedicao ? "--" : textoDaRegra(estado.regras[medicao.folha]);
}

// O cartão acompanha o relógio, mas só é reescrito quando algo que ele mostra muda: outro fluxo, uma medição nova do
// fluxo ou uma previsão nova conferida (o relógio passou do `t_futuro` dela).
function atualizarCartao(estado, elementos, partes) {
  const f = estado.selecionado;
  const { tempo } = estado;
  const indice = f === null ? -1 : ultimaDoFluxo(tempo, f);
  const indiceConferida = f === null ? -1 : ultimaConferidaDoFluxo(tempo, f);
  const medicao = indice < 0 ? null : tempo.medicoes[indice];
  const chave = `${f}|${indice}|${indiceConferida}`;
  if (chave === partes.cartao.chave) {
    return;
  }
  const campos = elementos.fluxo;
  if (f !== partes.cartao.fluxo) {
    campos.vazio.hidden = f !== null;
    campos.corpo.hidden = f === null;
    if (f !== null) {
      escreverRotaDoCartao(campos, estado.fluxos[f]);
    }
  }
  if (f !== null) {
    const conferida = indiceConferida < 0 ? null : tempo.medicoes[indiceConferida];
    escreverMedicaoDoCartao(estado, campos, partes.cartao.valoresDeX, medicao, conferida);
  }
  partes.cartao.chave = chave;
  partes.cartao.fluxo = f;
}

export { atualizarCartao, montarColunasDoCartao };
