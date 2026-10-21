// Historico.tsx: a tela "Histórico de previsões": o que cada pedido mandou, o que o modelo respondeu e de onde veio o pedido
// (`GET /api/previsoes`), da mais nova para a mais antiga, 25 por página.

import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { ErroDaApi, listarPrevisoes, type PaginaDePrevisoes } from "./api";

const PREVISOES_POR_PAGINA = 25;

/** "2026-10-20T12:01:50.3601708Z" vira "2026-10-20 12:01:50" (UTC). */
export function textoDaData(iso: string): string {
  return new Date(iso).toISOString().slice(0, 19).replace("T", " ");
}

/** Até duas casas, sem zeros à direita; ausente vira um traço. */
function numero(valor: number | null): string {
  return valor === null ? "—" : String(Number(valor.toFixed(2)));
}

const porcentagem = (valor: number): string => `${(valor * 100).toFixed(1)}%`;

type Estado = { tipo: "carregando" } | { tipo: "erro"; mensagem: string } | { tipo: "pronto"; pagina: PaginaDePrevisoes };

export function Historico() {
  const [busca] = useSearchParams();
  const numeroDaPagina = Math.max(1, Number.parseInt(busca.get("pagina") ?? "1", 10) || 1);
  const [estado, setEstado] = useState<Estado>({ tipo: "carregando" });

  useEffect(() => {
    const controle = new AbortController();
    setEstado({ tipo: "carregando" });
    listarPrevisoes(numeroDaPagina, PREVISOES_POR_PAGINA, controle.signal).then(
      (pagina) => setEstado({ tipo: "pronto", pagina }),
      (erro: unknown) => {
        if (!controle.signal.aborted) {
          setEstado({ tipo: "erro", mensagem: erro instanceof ErroDaApi ? erro.message : "Não consegui carregar o histórico." });
        }
      },
    );
    return () => controle.abort();
  }, [numeroDaPagina]);

  if (estado.tipo === "carregando") {
    return (
      <>
        <h1>Histórico de previsões</h1>
        <p className="sub" role="status">
          Carregando...
        </p>
      </>
    );
  }
  if (estado.tipo === "erro") {
    return (
      <>
        <h1>Histórico de previsões</h1>
        <div className="aviso" role="alert">
          {estado.mensagem}
        </div>
      </>
    );
  }

  const { total, itens } = estado.pagina;
  const totalDePaginas = Math.max(1, Math.ceil(total / PREVISOES_POR_PAGINA));
  return (
    <>
      <h1>Histórico de previsões</h1>
      <p className="sub">
        {total} {total === 1 ? "previsão guardada" : "previsões guardadas"}, da mais nova para a mais antiga.
      </p>

      {total === 0 ? (
        <p className="cartao">
          Ainda não há previsões. Faça a primeira em <Link to="/testar">Testar o modelo</Link>.
        </p>
      ) : (
        <>
          <div className="cartao rolagem">
            <table>
              <thead>
                <tr>
                  <th>Quando (UTC)</th>
                  <th>Classe</th>
                  <th>OK</th>
                  <th>RISCO</th>
                  <th>FALHA</th>
                  <th>z</th>
                  <th>Aumento %</th>
                  <th>Perda %</th>
                  <th>Origem</th>
                </tr>
              </thead>
              <tbody>
                {itens.map(({ previsao, entrada, origem }) => (
                  <tr key={previsao.id}>
                    <td>{textoDaData(previsao.criadaEmUtc)}</td>
                    <td>
                      <span className={`classe classe-${previsao.classe}`}>{previsao.classe}</span>
                    </td>
                    <td>{porcentagem(previsao.probabilidades.OK)}</td>
                    <td>{porcentagem(previsao.probabilidades.RISCO)}</td>
                    <td>{porcentagem(previsao.probabilidades.FALHA)}</td>
                    <td>{numero(entrada.z_robusto)}</td>
                    <td>{numero(entrada.aumento_pct)}</td>
                    <td>{numero(entrada.perda_pct)}</td>
                    <td>{origem}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="paginas">
            {numeroDaPagina > 1 ? <Link to={`/historico?pagina=${numeroDaPagina - 1}`}>← Mais novas</Link> : null}
            <span>
              Página {numeroDaPagina} de {totalDePaginas}
            </span>
            {numeroDaPagina < totalDePaginas ? <Link to={`/historico?pagina=${numeroDaPagina + 1}`}>Mais antigas →</Link> : null}
          </div>
        </>
      )}
    </>
  );
}
