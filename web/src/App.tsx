// App.tsx: as rotas do site. O servidor Go entrega o mesmo index.html em `/`, `/testar` e `/historico`; o react-router escolhe a tela.

import { Link, Route, Routes } from "react-router";
import { Historico } from "./paginas/Historico";
import { PaginaApi } from "./paginas/PaginaApi";
import { Testar } from "./paginas/Testar";
import { PaginaDoMapa } from "./replay/PaginaDoMapa";

function NaoEncontrada() {
  return (
    <PaginaApi titulo="Página não encontrada">
      <h1>Página não encontrada</h1>
      <p className="sub">
        Volte ao <Link to="/">mapa</Link>.
      </p>
    </PaginaApi>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<PaginaDoMapa />} />
      <Route
        path="/testar"
        element={
          <PaginaApi titulo="Testar o modelo">
            <Testar />
          </PaginaApi>
        }
      />
      <Route
        path="/historico"
        element={
          <PaginaApi titulo="Histórico">
            <Historico />
          </PaginaApi>
        }
      />
      <Route path="*" element={<NaoEncontrada />} />
    </Routes>
  );
}
