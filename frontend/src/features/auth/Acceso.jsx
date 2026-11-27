import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ShieldCheck, Waves, Eye, EyeOff } from "lucide-react";
import { api, renovarCsrf } from "../../services/api";
import { useAplicacion } from "../../app/context";
import { Marca, Campo, CajaError, Enviar } from "../../components/ui";
export default function Acceso({ register = false }) {
  const { user, setUser } = useAplicacion(),
    navigate = useNavigate();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [visible, setVisible] = useState(false);
  if (user) return <Navigate to="/app" replace />;
  async function enviarFormulario(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const form = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await renovarCsrf();
      const result = await api(register ? "/auth/registro" : "/auth/login", {
        method: "POST",
        body: form,
      });
      setUser(result.user);
      navigate("/app");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-page">
      <section className="auth-story">
        <Marca light />
        <div>
          <span className="eyebrow">TU HOGAR, MEJOR PREPARADO</span>
          <h1>
            Tranquilidad
            <br />
            gota a gota.
          </h1>
          <p>
            Organiza tus reservas y prepara un plan para los días en que el agua haga
            una pausa.
          </p>
          <Waves className="auth-waves" size={150} strokeWidth={0.8} />
        </div>
        <small>Hecho para los hogares de Arequipa.</small>
      </section>
      <main className="auth-content">
        <Link to="/" className="back-link">
          Volver al inicio
        </Link>
        <div className="auth-form">
          <span className="section-icon">
            <ShieldCheck size={25} />
          </span>
          <h1>{register ? "Empieza con tu hogar" : "Qué bueno verte de nuevo"}</h1>
          <p>
            {register
              ? "Crea tu cuenta y lleva el control de tus reservas."
              : "Ingresa para continuar con tu planificación."}
          </p>
          <CajaError message={error} />
          <form onSubmit={enviarFormulario}>
            {register && (
              <Campo
                label="Tu nombre"
                name="name"
                required
                minLength={2}
                maxLength={80}
                autoComplete="name"
                placeholder="¿Cómo te llamas?"
              />
            )}
            <Campo
              label="Correo electrónico"
              name="email"
              type="email"
              maxLength={254}
              required
              autoComplete="email"
              placeholder="nombre@correo.com"
            />
            <Campo
              label="Contraseña"
              hint={
                register ? "Usa al menos 10 caracteres. Puedes incluir espacios." : null
              }
            >
              <span className="password-input">
                <input
                  className="form-control"
                  name="password"
                  type={visible ? "text" : "password"}
                  required
                  minLength={register ? 10 : 1}
                  maxLength={128}
                  autoComplete={register ? "new-password" : "current-password"}
                />
                <button
                  type="button"
                  onClick={() => setVisible(!visible)}
                  aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
                >
                  {visible ? <EyeOff size={19} /> : <Eye size={19} />}
                </button>
              </span>
            </Campo>
            <Enviar busy={busy}>
              {register ? "Crear mi cuenta" : "Iniciar sesión"}
            </Enviar>
          </form>
          <p className="auth-switch">
            {register ? "¿Ya tienes una cuenta?" : "¿Es tu primera visita?"}{" "}
            <Link to={register ? "/login" : "/registro"}>
              {register ? "Inicia sesión" : "Crea tu cuenta"}
            </Link>
          </p>
          <div className="auth-note">
            <ShieldCheck size={17} />
            Los datos de tu hogar pertenecen a tu espacio privado.
          </div>
        </div>
      </main>
    </div>
  );
}
