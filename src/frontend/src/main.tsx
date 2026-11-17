import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ProveedorAvisos } from "./componentes/Avisos";
import { Aplicacion } from "./rutas/Aplicacion";
import "./componentes/estilos.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <ProveedorAvisos>
        <Aplicacion />
      </ProveedorAvisos>
    </BrowserRouter>
  </React.StrictMode>
);
