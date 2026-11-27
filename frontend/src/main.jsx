import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { useEffect } from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/theme.css";
import { ProveedorAplicacion } from "./app/context";
import Estructura, { RequiereSesion } from "./app/Estructura";
import Inicio from "./features/public/Inicio";
import Acceso from "./features/auth/Acceso";
import Perfil from "./features/auth/Perfil";
import Resumen from "./features/home/Resumen";
import Hogar from "./features/home/Hogar";
import Recipientes from "./features/water/Recipientes";
import Movimientos from "./features/water/Movimientos";
import Planes from "./features/plans/Planes";
import { ResumenAdmin, UsuariosAdmin, AuditoriaAdmin } from "./features/admin/Admin";
import {
  Cortes,
  Abastecimiento,
  Fuentes,
  FuentesAdmin,
} from "./features/fuentes/Fuentes";
function ReiniciarDesplazamiento() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
    document.title = `AguaReserva AQP · ${pathname.startsWith("/admin") ? "Administración" : pathname.startsWith("/app") ? "Mi hogar" : "Cada gota cuenta"}`;
  }, [pathname]);
  return null;
}
function Aplicacion() {
  return (
    <BrowserRouter>
      <ProveedorAplicacion>
        <ReiniciarDesplazamiento />
        <Routes>
          <Route path="/" element={<Inicio />} />
          <Route path="/login" element={<Acceso />} />
          <Route path="/registro" element={<Acceso register />} />
          <Route element={<RequiereSesion />}>
            <Route element={<Estructura />}>
              <Route path="/app" element={<Resumen />} />
              <Route path="/app/hogar" element={<Hogar />} />
              <Route path="/app/recipientes" element={<Recipientes />} />
              <Route path="/app/movimientos" element={<Movimientos />} />
              <Route path="/app/planes" element={<Planes />} />
              <Route path="/app/cortes" element={<Cortes />} />
              <Route path="/app/abastecimiento" element={<Abastecimiento />} />
              <Route path="/app/fuentes" element={<Fuentes />} />
              <Route path="/app/perfil" element={<Perfil />} />
              <Route element={<RequiereSesion admin />}>
                <Route path="/admin/fuentes" element={<FuentesAdmin />} />
                <Route path="/admin" element={<ResumenAdmin />} />
                <Route path="/admin/usuarios" element={<UsuariosAdmin />} />
                <Route path="/admin/auditoria" element={<AuditoriaAdmin />} />
              </Route>
            </Route>
          </Route>
          <Route
            path="*"
            element={
              <main className="not-found">
                <h1>Esta página no existe</h1>
                <p>Volvamos a un lugar conocido.</p>
                <Link className="btn btn-primary" to="/">
                  Volver al inicio
                </Link>
              </main>
            }
          />
        </Routes>
      </ProveedorAplicacion>
    </BrowserRouter>
  );
}
createRoot(document.getElementById("root")).render(<Aplicacion />);
