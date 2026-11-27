import { Link } from "react-router-dom";
import {
  Droplets,
  House,
  MapPin,
  ShieldCheck,
  ClipboardCheck,
  Cylinder,
  Waves,
  Compass,
  Check,
} from "lucide-react";
import { Marca, useDatos, formatearLitros, CajaError } from "../../components/ui";
import { useAplicacion } from "../../app/context";
export default function Inicio() {
  const { user } = useAplicacion(),
    { data, error, loading, reload } = useDatos("/publico/estadisticas");
  return (
    <div className="landing">
      <nav className="landing-nav page-width">
        <Marca />
        <div className="landing-nav-links">
          <a href="#como-funciona">Cómo funciona</a>
          <a href="#comunidad">La comunidad</a>
        </div>
        <div className="d-flex gap-2">
          {user ? (
            <Link className="btn btn-primary" to="/app">
              Ir a mi hogar
            </Link>
          ) : (
            <>
              <Link className="btn btn-quiet" to="/login">
                Iniciar sesión
              </Link>
              <Link className="btn btn-primary" to="/registro">
                Crear cuenta
              </Link>
            </>
          )}
        </div>
      </nav>
      <main>
        <section className="hero page-width">
          <div className="hero-copy">
            <span className="hero-badge">
              <span className="online-dot" />
              PENSADO PARA AREQUIPA
            </span>
            <h1>
              Cuida tu agua.
              <br />
              Prepara tu <span>tranquilidad.</span>
            </h1>
            <p>
              Conoce tus reservas, organiza el consumo y crea un plan para que tu hogar
              esté mejor preparado ante un corte de agua.
            </p>
            <div className="hero-actions">
              <Link className="btn btn-primary btn-lg" to={user ? "/app" : "/registro"}>
                <Droplets size={20} />
                Organizar mi reserva
              </Link>
              <a className="btn btn-outline-secondary btn-lg" href="#como-funciona">
                Conocer el proyecto
              </a>
            </div>
            <div className="hero-checks">
              <span>
                <Check size={17} />
                Tu hogar en un solo lugar
              </span>
              <span>
                <Check size={17} />
                Sin historial previo
              </span>
            </div>
          </div>
          <div className="hero-art" aria-label="Ilustración de una reserva de agua">
            <div className="art-orbit orbit-one" />
            <div className="art-orbit orbit-two" />
            <div className="art-dot dot-one" />
            <div className="art-dot dot-two" />
            <svg className="misti" viewBox="0 0 500 220" aria-hidden="true">
              <path
                d="M0 210 100 155 170 185 283 45 420 190 500 155 500 220H0Z"
                fill="#c8e8e7"
              />
              <path d="m238 102 45-57 49 60-32-12-17 13-22-16Z" fill="#edf9f6" />
            </svg>
            <div className="floating-note note-top">
              <span className="note-icon">
                <ShieldCheck size={23} />
              </span>
              <div>
                Un hogar preparado<small>Empieza con un buen plan</small>
              </div>
            </div>
            <div className="illustrated-tank">
              <div className="tank-lid" />
              <div className="tank-body">
                <div className="tank-water">
                  <div className="water-surface" />
                  <span className="bubble b1" />
                  <span className="bubble b2" />
                  <span className="bubble b3" />
                </div>
                <div className="tank-label">
                  <Droplets size={45} />
                  <span>
                    Cada gota
                    <br />
                    <strong>cuenta.</strong>
                  </span>
                </div>
                <div className="tank-scale" />
              </div>
              <div className="tank-base" />
            </div>
            <div className="floating-note note-bottom">
              <span className="note-icon blue">
                <Compass size={24} />
              </span>
              <div>
                De la reserva a la acción
                <small>Simula, compara y planifica</small>
              </div>
            </div>
            <span className="art-caption">AguaReserva AQP</span>
          </div>
        </section>
        <section id="comunidad" className="community">
          <div className="page-width">
            <div className="section-heading">
              <div>
                <span className="eyebrow">UNA COMUNIDAD MÁS PREPARADA</span>
                <h2>Pequeñas acciones. Un mejor mañana.</h2>
              </div>
              <span className="live-label">
                <i className="online-dot" />
                Datos registrados en la plataforma
              </span>
            </div>
            <CajaError message={error} retry={reload} />
            <div className="public-stats">
              {[
                [House, "Hogares registrados", data?.households, ""],
                [MapPin, "Distritos representados", data?.districts, ""],
                [Cylinder, "Capacidad registrada", data?.capacity, " L"],
                [ClipboardCheck, "Hogares con un plan", data?.with_plan, ""],
              ].map(([Icon, label, value, unit]) => (
                <div className="public-stat" key={label}>
                  <Icon size={24} />
                  <strong>
                    {loading ? "…" : formatearLitros(value)}
                    <small>{value != null ? unit : ""}</small>
                  </strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            <p className="privacy-note">
              <ShieldCheck size={14} />
              Mostramos información agregada. Los detalles se habilitan a partir de 5
              hogares. No publicamos datos personales.
            </p>
          </div>
        </section>
        <section id="como-funciona" className="how-section page-width">
          <span className="eyebrow">SIMPLE DESDE LA PRIMERA GOTA</span>
          <h2>Un plan de agua, en tres pasos.</h2>
          <p className="section-subtitle">
            Tú conoces tu hogar. AguaReserva te ayuda a organizarlo.
          </p>
          <div className="how-grid">
            {[
              [
                House,
                "01",
                "Conoce tu reserva",
                "Registra tu hogar y cuánto agua almacenas en cada recipiente.",
              ],
              [
                Waves,
                "02",
                "Lleva el control",
                "Anota recargas y consumos. Consulta tus saldos y movimientos.",
              ],
              [
                Compass,
                "03",
                "Prepara un plan",
                "Simula un corte y descubre cuánto necesitas reponer para afrontarlo.",
              ],
            ].map(([Icon, num, title, text]) => (
              <article className="how-card" key={num}>
                <div>
                  <span className="section-icon">
                    <Icon size={25} />
                  </span>
                  <span className="step-number">{num}</span>
                </div>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="landing-cta page-width">
          <div>
            <span className="eyebrow">HOY ES UN BUEN DÍA PARA EMPEZAR</span>
            <h2>Más claridad para cuidar tu reserva.</h2>
            <p>El primer paso es registrar tu hogar.</p>
          </div>
          <Link to={user ? "/app" : "/registro"} className="btn btn-white btn-lg">
            Empezar mi planificación
          </Link>
        </section>
      </main>
      <footer className="landing-footer page-width">
        <Marca />
        <span>Proyecto académico · Arequipa, Perú · 2026</span>
      </footer>
    </div>
  );
}
