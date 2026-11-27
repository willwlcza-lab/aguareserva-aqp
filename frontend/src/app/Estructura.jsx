import { useState } from "react";
import { Link, NavLink, Navigate, Outlet } from "react-router-dom";
import {
  Bell,
  MapPin,
  Database,
  LayoutDashboard,
  House,
  Cylinder,
  ArrowDownUp,
  Compass,
  UserRound,
  LogOut,
  ShieldCheck,
  Waves,
  Menu,
  X,
  Users,
  ScrollText,
  ExternalLink,
} from "lucide-react";
import { useAplicacion } from "./context";
import { Marca, CajaError, Cargando } from "../components/ui";
export function RequiereSesion({ admin = false }) {
  const { user, loading, bootError, boot } = useAplicacion();
  if (loading) return <Cargando />;
  if (bootError)
    return (
      <div className="container py-5">
        <Marca />
        <CajaError message={bootError} retry={boot} />
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  if (admin && user.role !== "ADMIN") return <Navigate to="/app" replace />;
  return <Outlet />;
}
export default function Estructura() {
  const { user, logout, notify } = useAplicacion();
  const [open, setOpen] = useState(false);
  const links = [
    ["/app", LayoutDashboard, "Mi resumen"],
    ["/app/hogar", House, "Mi hogar"],
    ["/app/recipientes", Cylinder, "Mis reservas"],
    ["/app/movimientos", ArrowDownUp, "Movimientos"],
    ["/app/cortes", Bell, "Avisos de cortes"],
    ["/app/abastecimiento", MapPin, "Abastecimiento"],
    ["/app/fuentes", Database, "Fuentes de datos"],
    ["/app/planes", Compass, "Plan de contingencia"],
  ];
  return (
    <div className="app-shell">
      <button
        className="mobile-menu"
        onClick={() => setOpen(!open)}
        aria-label={open ? "Cerrar menú" : "Abrir menú"}
      >
        {open ? <X /> : <Menu />}
      </button>
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <Marca />
        <div className="workspace-label">ESPACIO PERSONAL</div>
        <nav aria-label="Navegación principal">
          {links.map(([to, Icon, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/app"}
              onClick={() => setOpen(false)}
            >
              <Icon size={20} />
              {label}
            </NavLink>
          ))}
          {user.role === "ADMIN" && (
            <>
              <div className="workspace-label">ADMINISTRACIÓN</div>
              <NavLink to="/admin" end onClick={() => setOpen(false)}>
                <ShieldCheck size={20} />
                Vista general
              </NavLink>
              <NavLink to="/admin/usuarios" onClick={() => setOpen(false)}>
                <Users size={20} />
                Usuarios
              </NavLink>
              <NavLink to="/admin/fuentes" onClick={() => setOpen(false)}>
                <Database size={20} />
                Fuentes y revisión
              </NavLink>
              <NavLink to="/admin/auditoria" onClick={() => setOpen(false)}>
                <ScrollText size={20} />
                Auditoría
              </NavLink>
            </>
          )}
        </nav>
        <div className="sidebar-tip">
          <Waves size={25} />
          <strong>Cada gota cuenta.</strong>
          <p>Una reserva bien planificada empieza con un registro.</p>
        </div>
        <div className="sidebar-bottom">
          <NavLink to="/app/perfil">
            <UserRound size={19} />
            Mi cuenta
          </NavLink>
          <Link to="/">
            <ExternalLink size={18} />
            Ver portada
          </Link>
          <button onClick={() => logout().catch((e) => notify(e.message))}>
            <LogOut size={18} />
            Cerrar sesión
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>
            <i className="online-dot" />
            Mi espacio de agua
          </span>
          <div className="user-chip">
            <span className="avatar">{user.name.charAt(0).toUpperCase()}</span>
            <span>
              {user.name}
              <small>
                {user.role === "ADMIN" ? "Administrador" : "Miembro de AguaReserva"}
              </small>
            </span>
          </div>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>AguaReserva AQP</span>
          <span>Proyecto académico · Noviembre 2026</span>
        </footer>
      </div>
    </div>
  );
}
