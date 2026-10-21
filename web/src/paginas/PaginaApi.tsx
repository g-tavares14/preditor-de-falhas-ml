// PaginaApi.tsx: a moldura das telas Testar e Histórico: o topo com os links e o conteúdo. O estilo (paginas.css) vale só dentro de
// `.api-pagina`, para não brigar com o estilo do mapa.

import { useEffect, type ReactNode } from "react";
import { Link } from "react-router";

export function PaginaApi({ titulo, children }: { titulo: string; children: ReactNode }) {
  useEffect(() => {
    const anterior = document.title;
    document.title = `${titulo} · Preditor de falhas`;
    return () => {
      document.title = anterior;
    };
  }, [titulo]);

  return (
    <div className="api-pagina">
      <header className="topo">
        <Link className="marca" to="/">
          Preditor de falhas de rede
        </Link>
        <nav>
          <Link to="/">Mapa</Link>
          <Link to="/testar">Testar o modelo</Link>
          <Link to="/historico">Histórico</Link>
          {/* Páginas que o servidor Go entrega (não são do app): link comum, com recarga. */}
          <a href="/swagger/">API</a>
          <a href="/api/modelo">Ficha do modelo</a>
        </nav>
      </header>
      <main>{children}</main>
    </div>
  );
}
