import { AlertasPersonales } from "../fuentes/Fuentes";
import { Link } from "react-router-dom";
import {
  Droplets,
  Cylinder,
  Users,
  Plus,
  Compass,
  Clock3,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { useAplicacion } from "../../app/context";
import {
  useDatos,
  TituloPagina,
  Cargando,
  CajaError,
  Vacio,
  Estadistica,
  NivelAgua,
  formatearLitros,
  TablaMovimientos,
  nombreEstado,
} from "../../components/ui";
export default function Resumen() {
  const { user } = useAplicacion(),
    { data, loading, error, reload } = useDatos("/hogares/mio/panel");
  if (loading) return <Cargando />;
  if (error) return <CajaError message={error} retry={reload} />;
  const firstName = user.name.split(" ")[0];
  if (!data.household)
    return (
      <>
        <AlertasPersonales />
        <TituloPagina
          eyebrow="BIENVENIDO A AGUARESERVA"
          title={`Hola, ${firstName}. Empecemos.`}
          text="Tu espacio para cuidar el agua que tienes y planificar la que necesitas."
        />
        <div className="onboarding-panel">
          <Vacio
            title="Un hogar preparado empieza aquí"
            text="Registra tu hogar, agrega tus recipientes y descubre cuánto pueden durar tus reservas."
            to="/app/hogar"
            button="Registrar mi hogar"
          />
          <div className="onboarding-steps">
            <span>01 · Tu hogar</span>
            <span>02 · Tus reservas</span>
            <span>03 · Tu primer plan</span>
          </div>
        </div>
      </>
    );
  const { household: h, plan24, containers } = data;
  const max = Math.max(10, ...data.chart.map((d) => d.liters || 0));
  return (
    <>
      <TituloPagina
        eyebrow="CADA GOTA CUENTA"
        title={`Hola, ${firstName}.`}
        text={`Así están las reservas de ${h.name}.`}
        action={
          <Link className="btn btn-primary" to="/app/movimientos">
            <Plus size={18} />
            Registrar movimiento
          </Link>
        }
      />
      <section className="dashboard-hero">
        <div>
          <span className="hero-badge">{h.district.toUpperCase()}</span>
          <h2>Tu agua, a simple vista.</h2>
          <p>
            Una reserva organizada te ayuda a tomar
            <br className="d-none d-lg-block" /> mejores decisiones para tu hogar.
          </p>
          <Link className="btn btn-white" to="/app/planes">
            <Compass size={19} />
            Preparar mi plan
          </Link>
        </div>
        <NivelAgua balance={data.total} capacity={data.capacity} />
        <div className="hero-watermark">
          <Droplets size={230} strokeWidth={0.6} />
        </div>
      </section>
      <div className="stats-grid">
        <Estadistica
          label="Agua disponible"
          value={formatearLitros(data.total)}
          suffix="L"
          icon={Droplets}
          detail="Total de los usos declarados"
        />
        <Estadistica
          label="Capacidad de almacenamiento"
          value={formatearLitros(data.capacity)}
          suffix="L"
          icon={Cylinder}
          detail={`${containers.length} recipiente${containers.length === 1 ? "" : "s"} activo${containers.length === 1 ? "" : "s"}`}
        />
        <Estadistica
          label="Integrantes del hogar"
          value={h.members}
          icon={Users}
          detail="Consumo estimado para todo el hogar"
        />
      </div>
      <div
        className={`notice ${plan24.status === "covered" ? "notice-success" : "notice-warning"}`}
      >
        {plan24.status === "covered" ? (
          <CheckCircle2 size={23} />
        ) : (
          <AlertTriangle size={23} />
        )}
        <div>
          <strong>{nombreEstado(plan24.status)} para las próximas 24 horas</strong>
          <p>
            {plan24.status === "covered"
              ? "Según tus estimaciones actuales. Actualiza los movimientos para mantener el cálculo al día."
              : plan24.status === "incomplete"
                ? "Completa o revisa el consumo diario en Mi hogar para obtener un cálculo útil."
                : "Uno o más usos tienen una reserva insuficiente. Revisa el plan de contingencia."}
          </p>
        </div>
        <Link to={plan24.status === "incomplete" ? "/app/hogar" : "/app/planes"}>
          Revisar
        </Link>
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <h2>Autonomía por uso</h2>
            <Clock3 size={20} />
          </div>
          <p className="muted">Basada en el consumo diario que declaraste.</p>
          {plan24.items.map((item) => (
            <div className="autonomy-row" key={item.water_type}>
              <span
                className={`usage-icon ${item.water_type === "other" ? "usage-other" : ""}`}
              >
                <Droplets size={22} />
              </span>
              <div>
                <strong>
                  {item.water_type === "drinking" ? "Consumo humano" : "Otros usos"}
                </strong>
                <small>
                  {formatearLitros(item.available)} L ·{" "}
                  {item.daily == null
                    ? "Falta estimación diaria"
                    : `${formatearLitros(item.daily)} L por día`}
                </small>
              </div>
              <b>
                {item.days == null ? "—" : formatearLitros(item.days)}
                <small>{item.days == null ? "sin cálculo" : "días"}</small>
              </b>
            </div>
          ))}
          <p className="fine-print">
            El uso declarado no certifica la calidad del agua. Los saldos de distintos
            usos no se intercambian en el cálculo.
          </p>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <h2>Consumo registrado</h2>
            <span className="badge-soft">Últimos 7 días</span>
          </div>
          <div
            className="consumption-chart"
            role="img"
            aria-label="Consumo registrado por día. Las marcas vacías indican días sin registro."
          >
            {data.chart.map((d) => (
              <div className="chart-column" key={d.date}>
                <span>{d.liters == null ? "—" : `${formatearLitros(d.liters)} L`}</span>
                <div className="chart-track">
                  <div
                    className={`chart-bar ${d.liters == null ? "no-data" : ""}`}
                    style={{
                      height:
                        d.liters == null
                          ? "3px"
                          : `${Math.max(3, (d.liters / max) * 100)}%`,
                    }}
                  />
                </div>
                <small>
                  {new Intl.DateTimeFormat("es-PE", {
                    weekday: "short",
                    timeZone: "UTC",
                  }).format(new Date(d.date))}
                </small>
              </div>
            ))}
          </div>
          <p className="chart-caption">
            <i className="legend-dot" />
            Litros registrados <span>— Sin registro; no significa consumo cero</span>
          </p>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Últimos movimientos</h2>
          <Link to="/app/movimientos" className="text-button">
            Ver historial
          </Link>
        </div>
        <TablaMovimientos rows={data.recent} />
      </section>
    </>
  );
}
