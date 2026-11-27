import { useState } from "react";
import { Users, House, Cylinder, ClipboardCheck, ShieldCheck } from "lucide-react";
import {
  TituloPagina,
  Estadistica,
  useDatos,
  Cargando,
  CajaError,
  formatearFecha,
} from "../../components/ui";
import { api } from "../../services/api";
import { useAplicacion } from "../../app/context";
export function ResumenAdmin() {
  const { data, loading, error, reload } = useDatos("/admin/resumen");
  if (loading) return <Cargando />;
  if (error) return <CajaError message={error} retry={reload} />;
  const max = Math.max(1, ...data.districts.map((d) => d.households));
  return (
    <>
      <TituloPagina
        eyebrow="ADMINISTRACIÓN"
        title="La comunidad, a simple vista"
        text="Indicadores de los registros de esta instalación."
      />
      <div className="stats-grid four">
        <Estadistica label="Cuentas" value={data.users} icon={Users} />
        <Estadistica label="Hogares" value={data.households} icon={House} />
        <Estadistica
          label="Recipientes activos"
          value={data.containers}
          icon={Cylinder}
        />
        <Estadistica
          label="Planes guardados"
          value={data.plans}
          icon={ClipboardCheck}
        />
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <h2>Hogares por distrito</h2>
          </div>
          {data.districts.length ? (
            data.districts.map((d) => (
              <div className="district-row" key={d.district}>
                <div>
                  <span>{d.district}</span>
                  <strong>{d.households}</strong>
                </div>
                <div className="district-track">
                  <span
                    style={{
                      width: `${(d.households / max) * 100}%`,
                    }}
                  />
                </div>
              </div>
            ))
          ) : (
            <p className="muted">Aún no hay hogares registrados.</p>
          )}
        </section>
        <section className="help-panel">
          <span className="section-icon">
            <ShieldCheck size={26} />
          </span>
          <h3>Una administración responsable</h3>
          <p>
            Gestiona el estado de las cuentas y revisa los eventos de auditoría. El
            saldo del agua se modifica desde la cuenta propietaria de cada hogar.
          </p>
          <p>
            Los indicadores cuentan los registros existentes, incluidos los ficticios si
            ejecutaste la carga de demostración.
          </p>
          <div className="notice notice-info">
            <p>
              Consulta avisos de Sedapar, datos complementarios de cortes y cisternas, y
              orientación de ONG en Fuentes y revisión.
            </p>
          </div>
        </section>
      </div>
    </>
  );
}
export function UsuariosAdmin() {
  const [page, setPage] = useState(0),
    { data, loading, error, reload } = useDatos(`/admin/usuarios?offset=${page * 100}`),
    { user, notify } = useAplicacion(),
    [busy, setBusy] = useState(""),
    [actionError, setActionError] = useState("");
  async function cambiarEstado(u) {
    if (
      !window.confirm(
        `¿${u.active ? "Desactivar" : "Activar"} la cuenta de ${u.name}?${u.active ? " Sus sesiones se cerrarán." : ""}`,
      )
    )
      return;
    setBusy(u.id);
    setActionError("");
    try {
      await api(`/admin/usuarios/${u.id}/estado`, {
        method: "PATCH",
        body: {
          active: !u.active,
        },
      });
      reload();
      notify("Estado de la cuenta actualizado.");
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <TituloPagina
        eyebrow="ADMINISTRACIÓN"
        title="Usuarios"
        text="Activa o desactiva cuentas. El registro público siempre crea usuarios comunes."
      />
      <CajaError message={actionError} />
      <section className="panel">
        {loading ? (
          <Cargando />
        ) : error ? (
          <CajaError message={error} retry={reload} />
        ) : (
          <>
            <div className="table-responsive">
              <table className="table aqp-table">
                <thead>
                  <tr>
                    <th>Usuario</th>
                    <th>Correo</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((u) => (
                    <tr key={u.id}>
                      <td>{u.name}</td>
                      <td>{u.email}</td>
                      <td>{u.role === "ADMIN" ? "Administrador" : "Usuario"}</td>
                      <td>
                        <span className={u.active ? "badge-soft" : "badge-warning"}>
                          {u.active ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="text-button"
                          disabled={!!busy || u.id === user.id}
                          onClick={() => cambiarEstado(u)}
                        >
                          {u.id === user.id
                            ? "Tu cuenta"
                            : busy === u.id
                              ? "Guardando…"
                              : u.active
                                ? "Desactivar"
                                : "Activar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination-row">
              <button
                className="btn btn-light"
                disabled={!page}
                onClick={() => setPage(page - 1)}
              >
                Anterior
              </button>
              <span>Página {page + 1}</span>
              <button
                className="btn btn-light"
                disabled={data.length < 100}
                onClick={() => setPage(page + 1)}
              >
                Siguiente
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
const actions = {
  "user.registered": "Cuenta registrada",
  "user.login": "Inicio de sesión",
  "user.profile_updated": "Perfil actualizado",
  "user.password_changed": "Contraseña cambiada",
  "admin.created_cli": "Administrador creado",
  "user.enabled": "Cuenta activada",
  "user.disabled": "Cuenta desactivada",
  "household.created": "Hogar registrado",
  "household.updated": "Hogar actualizado",
  "container.created": "Recipiente registrado",
  "container.updated": "Recipiente actualizado",
  "container.archived": "Recipiente archivado",
  "movement.created": "Movimiento registrado",
  "plan.saved": "Plan guardado",
};
export function AuditoriaAdmin() {
  const [page, setPage] = useState(0),
    { data, loading, error, reload } = useDatos(
      `/admin/auditoria?offset=${page * 100}`,
    );
  return (
    <>
      <TituloPagina
        eyebrow="ADMINISTRACIÓN"
        title="Registro de auditoría"
        text="Trazabilidad de las operaciones. No se registran contraseñas ni tokens."
      />
      <section className="panel">
        {loading ? (
          <Cargando />
        ) : error ? (
          <CajaError message={error} retry={reload} />
        ) : (
          <>
            <div className="table-responsive">
              <table className="table aqp-table">
                <thead>
                  <tr>
                    <th>Fecha (Lima)</th>
                    <th>Responsable</th>
                    <th>Operación</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((e) => (
                    <tr key={e.id}>
                      <td>{formatearFecha(e.created_at)}</td>
                      <td>{e.actor}</td>
                      <td>{actions[e.action] || e.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!data.length && <p className="muted">Todavía no hay eventos.</p>}
            <div className="pagination-row">
              <button
                className="btn btn-light"
                disabled={!page}
                onClick={() => setPage(page - 1)}
              >
                Anterior
              </button>
              <span>Página {page + 1}</span>
              <button
                className="btn btn-light"
                disabled={data.length < 100}
                onClick={() => setPage(page + 1)}
              >
                Siguiente
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
