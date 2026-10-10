// cartao.js: o cartão da conexão selecionada (SPEC-visualizacao.md, "Comportamento da página", item 6, último ponto).
//
// Mostra, em palavras simples, a rota da conexão, a última medição dela até o instante do relógio e a última previsão que
// o relógio já conferiu. Só escreve com textContent. Não calcula métrica: tudo já vem no JSON.

import { acertou } from "./placar.js";
import { ehTimeout, ultimaConferidaDoFluxo, ultimaDoFluxo } from "./tempo.js";
import { TEXTO_ACERTOU, TEXTO_ERROU, criarCelula, criarChip, detalhesDoFluxo, formatarInstante, nomeDoPais } from "./comum.js";

const SEM_FUTURO = "sem como conferir (faltou medição depois)";
const SEM_CONFERIDA = "nenhuma previsão conferida ainda";

// "123,5 ms" ou "sem resposta" (a medição em que nenhum pacote voltou).
function textoDoRtt(medicao) {
  return ehTimeout(medicao) ? "sem resposta" : `${medicao.rtt.toLocaleString("pt-BR", { maximumFractionDigits: 1, useGrouping: false })} ms`;
}

// Situação da previsão da ÚLTIMA medição da conexão. O cartão não adianta o futuro: o `futuro` dela só aparece na linha
// "última previsão conferida" (abaixo), depois que o relógio passa do `t_futuro`. A última medição que já aconteceu sempre
// tem o futuro adiante (ele é a 3ª medição seguinte, que ainda não aconteceu), então aqui só há "aguardando" ou "sem futuro".
function escreverSituacao(destino, medicao) {
  if (medicao === null) {
    destino.textContent = "ainda sem medição neste instante";
  } else if (!medicao.conferivel) {
    destino.textContent = SEM_FUTURO;
  } else {
    destino.textContent = `será conferida às ${formatarInstante(medicao.t_futuro).hora} (UTC)`;
  }
}

// A previsão mais recente da conexão que o relógio já conferiu: a hora (UTC) em que foi feita, o que o sistema previu, o que
// aconteceu e o resultado (✓ Acertou ou ✗ Errou, com texto e símbolo: nunca só cor). `medicao` é null se não há nenhuma.
function escreverConferida(campos, medicao) {
  campos.conferida.classList.remove("fluxo-acertou", "fluxo-errou");
  if (medicao === null) {
    campos.conferida.textContent = SEM_CONFERIDA;
    return;
  }
  const ok = acertou(medicao);
  campos.conferida.classList.add(ok ? "fluxo-acertou" : "fluxo-errou");
  const hora = criarCelula("span", `${formatarInstante(medicao.t).hora} `, "numero"); // quando a previsão foi feita (UTC)
  campos.conferida.replaceChildren(hora, "previu ", criarChip(medicao.previsto), ", aconteceu ", criarChip(medicao.futuro), ` ${ok ? "✓" : "✗"} ${ok ? TEXTO_ACERTOU : TEXTO_ERROU}`);
}

// A parte do cartão que só muda quando se escolhe outra conexão: a rota (ponto de medição, destino, cabos, km) e os tempos de referência.
function escreverRotaDoCartao(campos, fluxo) {
  const { sonda, cidade } = detalhesDoFluxo(fluxo);
  const trechos = fluxo.trechos.map((trecho) => trecho.nome).join(" → ");
  const pais = nomeDoPais(fluxo.pais);
  campos.titulo.textContent = `Ponto ${sonda} (Brasil) → ${cidade === pais ? cidade : `${cidade}, ${pais}`}`; // "Singapura", não "Singapura, Singapura"
  campos.opcao.textContent = `Rota ilustrativa: ${fluxo.opcao}`;
  campos.trechos.textContent = `Passa por: ${trechos}`;
  campos.trechos.title = trechos;
  // Sem separador de milhar ("19.833" seria lido como decimal), como no cartão do trecho.
  campos.km.textContent = `${Math.round(fluxo.km)} km`;
  const minimo = `${fluxo.rtt_minimo_ms.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ms`;
  const mediana = fluxo.mediana_ms === null ? "sem referência" : `${fluxo.mediana_ms.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ms`;
  campos.rtt.textContent = `mínimo ${minimo} × normal ${mediana}`;
}

// A parte do cartão que acompanha o relógio: a última medição da conexão e a última previsão conferida. `conferida` é a
// medição da última previsão já conferida da conexão, ou null.
function escreverMedicaoDoCartao(campos, medicao, conferida) {
  const semMedicao = medicao === null;
  campos.hora.textContent = semMedicao ? "--" : `${formatarInstante(medicao.t).hora} UTC`;
  campos.rttAtual.textContent = semMedicao ? "--" : textoDoRtt(medicao);
  campos.atual.replaceChildren(...(semMedicao ? ["--"] : [criarChip(medicao.atual)]));
  campos.previsto.replaceChildren(...(semMedicao ? ["--"] : [criarChip(medicao.previsto)]));
  escreverSituacao(campos.situacao, medicao);
  escreverConferida(campos, conferida);
}

// O cartão acompanha o relógio, mas só é reescrito quando algo que ele mostra muda: outra conexão, uma medição nova dela
// ou uma previsão nova conferida (o relógio passou do `t_futuro` dela).
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
    escreverMedicaoDoCartao(campos, medicao, conferida);
  }
  partes.cartao.chave = chave;
  partes.cartao.fluxo = f;
}

export { atualizarCartao };
