// Testar.tsx: a tela "Testar o modelo": o formulário com as 10 colunas, a previsão da Random Forest 12 minutos à frente e as barras de
// probabilidade. Fala com `POST /api/previsoes?origem=formulario`; cada previsão fica no histórico.

import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import type { Classe } from "../tipos";
import { ErroDaApi, NOMES_DAS_COLUNAS, criarPrevisao, type Entrada, type NomeDaColuna, type PrevisaoResposta } from "./api";
import { COLUNAS, EXEMPLOS } from "./colunas";

/** O formulário guarda texto (campo vazio = valor ausente); só no envio vira número ou null. */
type Valores = Record<NomeDaColuna, string>;

const VAZIO: Valores = Object.fromEntries(NOMES_DAS_COLUNAS.map((nome) => [nome, ""])) as Valores;

function valoresDoExemplo(entrada: Entrada): Valores {
  return Object.fromEntries(NOMES_DAS_COLUNAS.map((nome) => [nome, entrada[nome] === null ? "" : String(entrada[nome])])) as Valores;
}

/** Campo vazio = ausente (null); o modelo aceita, e imputar um zero esconderia um timeout (RFC §8.3). */
function paraEntrada(valores: Valores): Entrada {
  return Object.fromEntries(NOMES_DAS_COLUNAS.map((nome) => [nome, valores[nome].trim() === "" ? null : Number(valores[nome])])) as Entrada;
}

const CLASSES_NA_ORDEM: Classe[] = ["OK", "RISCO", "FALHA"];

function Resultado({ previsao }: { previsao: PrevisaoResposta }) {
  return (
    <section className="cartao" aria-live="polite">
      <p>
        Previsão para daqui a 12 minutos: <span className={`classe classe-${previsao.classe}`}>{previsao.classe}</span>
      </p>
      {CLASSES_NA_ORDEM.map((classe) => {
        const pct = previsao.probabilidades[classe] * 100;
        return (
          <div className={`barra classe-${classe}`} key={classe}>
            <span className="nome">{classe}</span>
            <span className="trilho">
              <span className="cheio" style={{ display: "block", width: `${pct.toFixed(1)}%` }}></span>
            </span>
            <span>{pct.toFixed(1)}%</span>
          </div>
        );
      })}
      <p className="sha">Modelo (SHA-256): {previsao.modeloSha256}</p>
    </section>
  );
}

export function Testar() {
  const [busca] = useSearchParams();
  const exemplo = busca.get("exemplo");
  const [valores, setValores] = useState<Valores>(() => (exemplo !== null && exemplo in EXEMPLOS ? valoresDoExemplo(EXEMPLOS[exemplo].entrada) : VAZIO));
  const [resultado, setResultado] = useState<PrevisaoResposta | null>(null);
  const [erros, setErros] = useState<Record<string, string[]>>({});
  const [falha, setFalha] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Escolher um exemplo preenche o formulário (e limpa o resultado e os erros da tentativa anterior).
  useEffect(() => {
    if (exemplo !== null && exemplo in EXEMPLOS) {
      setValores(valoresDoExemplo(EXEMPLOS[exemplo].entrada));
      setResultado(null);
      setErros({});
      setFalha(null);
    }
  }, [exemplo]);

  async function enviar(evento: FormEvent<HTMLFormElement>): Promise<void> {
    evento.preventDefault();
    setEnviando(true);
    setResultado(null);
    setErros({});
    setFalha(null);
    try {
      setResultado(await criarPrevisao(paraEntrada(valores)));
    } catch (erro) {
      if (erro instanceof ErroDaApi && erro.status === 400 && erro.problema?.errors) {
        setErros(erro.problema.errors); // um erro por coluna, ao lado do campo
      } else if (erro instanceof ErroDaApi && erro.status === 503) {
        // A página explica; nunca mostra uma previsão que não veio do modelo.
        setFalha(`O serviço do modelo não respondeu: ${erro.problema?.detail ?? erro.message} Nada foi gravado.`);
      } else {
        setFalha(`${erro instanceof Error ? erro.message : "Não consegui fazer a previsão."} Nada foi gravado.`);
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <h1>Testar o modelo</h1>
      <p className="sub">
        Informe as métricas de uma rota agora; a Random Forest prevê a classe <strong>12 minutos à frente</strong>. Campo vazio = valor ausente (o modelo aceita).
      </p>

      {falha !== null ? (
        <div className="aviso" role="alert">
          {falha}
        </div>
      ) : null}

      {resultado !== null ? <Resultado previsao={resultado} /> : null}

      <form className="cartao" onSubmit={(evento) => void enviar(evento)} noValidate>
        <p className="exemplos">
          Exemplos:{" "}
          {Object.entries(EXEMPLOS).map(([chave, { titulo }]) => (
            <span key={chave}>
              <Link to={`/testar?exemplo=${chave}`}>{titulo}</Link>
              {"  "}
            </span>
          ))}
        </p>
        <div className="grade">
          {COLUNAS.map((coluna) => (
            <label key={coluna.nome}>
              {coluna.titulo} <small>{coluna.ajuda}</small>
              <input
                type="number"
                name={coluna.nome}
                step={coluna.passo}
                value={valores[coluna.nome]}
                onChange={(evento) => setValores({ ...valores, [coluna.nome]: evento.target.value })}
              />
              {erros[coluna.nome] ? <span className="erro-campo">{erros[coluna.nome].join(" ")}</span> : null}
            </label>
          ))}
        </div>
        <div className="acoes">
          <button type="submit" disabled={enviando}>
            {enviando ? "Prevendo..." : "Prever"}
          </button>
          <span className="sub" style={{ margin: 0 }}>
            Cada previsão fica no <Link to="/historico">histórico</Link>.
          </span>
        </div>
      </form>
    </>
  );
}
