import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, UserRound } from "lucide-react";
import { useAplicacion } from "../../app/context";
import { api, renovarCsrf } from "../../services/api";
import { TituloPagina, Campo, Enviar, CajaError } from "../../components/ui";
export default function Perfil() {
  const { user, setUser, notify } = useAplicacion(),
    navigate = useNavigate();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function guardarPerfil(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const u = await api("/perfil", {
        method: "PATCH",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      setUser(u);
      notify("Perfil actualizado.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function cambiarContrasena(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/perfil/cambiar-contrasena", {
        method: "POST",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      setUser(null);
      await renovarCsrf();
      notify("Contraseña actualizada. Inicia sesión nuevamente.");
      navigate("/login");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <TituloPagina
        eyebrow="TU ESPACIO PERSONAL"
        title="Mi cuenta"
        text="Gestiona tus datos y la seguridad de tu acceso."
      />
      <CajaError message={error} />
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <h2>
              <UserRound size={21} />
              Mis datos
            </h2>
          </div>
          <form onSubmit={guardarPerfil}>
            <Campo
              label="Nombre"
              name="name"
              defaultValue={user.name}
              required
              minLength={2}
              maxLength={80}
            />
            <Campo
              label="Correo de acceso"
              value={user.email}
              readOnly
              hint="El cambio de correo no está habilitado en este avance."
            />
            <div className="role-label">
              Rol: {user.role === "ADMIN" ? "Administrador" : "Usuario"}
            </div>
            <Enviar busy={busy} />
          </form>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h2>
              <ShieldCheck size={21} />
              Cambiar contraseña
            </h2>
          </div>
          <form onSubmit={cambiarContrasena}>
            <Campo
              label="Contraseña actual"
              name="current_password"
              type="password"
              required
              autoComplete="current-password"
            />
            <Campo
              label="Nueva contraseña"
              name="new_password"
              type="password"
              minLength={10}
              maxLength={128}
              required
              autoComplete="new-password"
              hint="Mínimo 10 caracteres. Se cerrarán tus sesiones activas."
            />
            <Enviar busy={busy}>Actualizar contraseña</Enviar>
          </form>
        </section>
      </div>
    </>
  );
}
