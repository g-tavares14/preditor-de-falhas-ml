// main.tsx: ponto de entrada do site. O servidor Go entrega o mesmo index.html em todas as rotas do app; o react-router escolhe a tela.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./App";
import "./estilo.css";
import "./paginas.css";

createRoot(document.getElementById("raiz") as HTMLElement).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
