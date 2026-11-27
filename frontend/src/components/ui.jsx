import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Droplets, AlertCircle, Plus, LoaderCircle } from "lucide-react";
import { api } from "../services/api";
const formatearLitros = (n) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("es-PE", {
        maximumFractionDigits: 2,
      }).format(n);
export { formatearLitros };
const formatearFecha = (d) =>
  new Intl.DateTimeFormat("es-PE", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "America/Lima",
  }).format(new Date(d));
export { formatearFecha };
const nombreUsoAgua = (t) =>
  t === "drinking" ? "Consumo humano · declarado" : "Otros usos";
export { nombreUsoAgua };
const nombreMovimiento = (k) =>
  ({
    initial: "Saldo inicial",
    refill: "Recarga",
    consumption: "Consumo",
    adjust_up: "Ajuste de entrada",
    adjust_down: "Ajuste de salida",
  })[k] || k;
export { nombreMovimiento };
const nombreEstado = (s) =>
  ({
    covered: "Reserva suficiente",
    deficit: "Necesita preparación",
    incomplete: "Completa tus estimaciones",
    unknown: "Sin estimación",
    no_demand: "Revisar consumo de 0 L",
  })[s] || s;
export { nombreEstado };
export function useDatos(path) {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [version, setVersion] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    api(path)
      .then((d) => {
        if (alive) setData(d);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, version]);
  return {
    data,
    error,
    loading,
    reload: () => setVersion((v) => v + 1),
  };
}
export function Marca({ light = false }) {
  return (
    <Link className={`brand ${light ? "brand-light" : ""}`} to="/">
      <span className="brand-icon">
        <Droplets size={24} />
      </span>
      <span>
        AguaReserva<small>AREQUIPA · AQP</small>
      </span>
    </Link>
  );
}
export function CajaError({ message, retry }) {
  return (
    message && (
      <div className="notice notice-error" role="alert">
        <AlertCircle size={20} />
        <div>
          {message}
          {retry && (
            <button className="text-button d-block" onClick={retry}>
              Volver a intentar
            </button>
          )}
        </div>
      </div>
    )
  );
}
export function Cargando() {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spin" size={28} />
      <span>Cargando tus datos…</span>
    </div>
  );
}
export function Vacio({ title, text, to, button }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Droplets size={28} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {to && (
        <Link to={to} className="btn btn-primary">
          <Plus size={18} />
          {button}
        </Link>
      )}
    </div>
  );
}
export function TituloPagina({ eyebrow, title, text, action }) {
  return (
    <div className="page-title">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {text && <p>{text}</p>}
      </div>
      {action}
    </div>
  );
}
export function Campo({ label, hint, children, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children || <input className="form-control" {...props} />}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Enviar({ busy, children = "Guardar cambios" }) {
  return (
    <button className="btn btn-primary" type="submit" disabled={busy}>
      {busy && <LoaderCircle className="spin" size={17} />}
      {busy ? "Guardando…" : children}
    </button>
  );
}
export function NivelAgua({ balance, capacity, small = false }) {
  const percentage =
    capacity > 0 ? Math.min(100, Math.max(0, (balance / capacity) * 100)) : 0;
  return (
    <div
      className={`water-gauge ${small ? "gauge-small" : ""}`}
      role="img"
      aria-label={`${formatearLitros(balance)} de ${formatearLitros(capacity)} litros, ${Math.round(percentage)} por ciento`}
    >
      <div className="gauge-lines" />
      <div
        className="water-fill"
        style={{
          height: `${percentage}%`,
        }}
      >
        <div className="water-surface" />
      </div>
      <div className="gauge-reading">
        <strong>
          {Math.round(percentage)}
          <span>%</span>
        </strong>
        <small>de capacidad</small>
      </div>
    </div>
  );
}
export function Estadistica({ label, value, suffix, icon: Icon, detail }) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span>{label}</span>
        {Icon && <Icon size={20} />}
      </div>
      <div className="stat-value">
        {value}
        <small>{suffix}</small>
      </div>
      {detail && <p>{detail}</p>}
    </div>
  );
}
export function TablaMovimientos({ rows }) {
  if (!rows?.length)
    return <p className="muted py-4">Todavía no hay movimientos registrados.</p>;
  return (
    <div className="table-responsive">
      <table className="table aqp-table">
        <thead>
          <tr>
            <th>Movimiento</th>
            <th>Recipiente</th>
            <th>Litros</th>
            <th>Saldo</th>
            <th>Fecha</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.id}>
              <td>
                <span
                  className={`dot ${m.kind === "consumption" || m.kind === "adjust_down" ? "dot-amber" : ""}`}
                />
                {nombreMovimiento(m.kind)}
                {m.reason && <small className="table-note">{m.reason}</small>}
              </td>
              <td>{m.container_name}</td>
              <td className="number">
                {m.kind === "consumption" || m.kind === "adjust_down" ? "−" : "+"}
                {formatearLitros(m.liters)} L
              </td>
              <td className="number">{formatearLitros(m.balance_after)} L</td>
              <td className="muted">{formatearFecha(m.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
