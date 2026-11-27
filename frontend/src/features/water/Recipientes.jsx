import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Cylinder, Archive, Pencil, X } from "lucide-react";
import {
  useDatos,
  TituloPagina,
  Cargando,
  CajaError,
  Vacio,
  Campo,
  Enviar,
  NivelAgua,
  formatearLitros,
  nombreUsoAgua,
} from "../../components/ui";
import { api } from "../../services/api";
import { useAplicacion } from "../../app/context";
export default function Recipientes() {
  const state = useDatos("/recipientes"),
    home = useDatos("/hogares/mio");
  const [form, setForm] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const { notify } = useAplicacion();
  if (state.loading || home.loading) return <Cargando />;
  if (state.error || home.error)
    return (
      <CajaError
        message={state.error || home.error}
        retry={() => {
          state.reload();
          home.reload();
        }}
      />
    );
  if (!home.data)
    return (
      <Vacio
        title="Primero, registra tu hogar"
        text="Así podrás asociar tus recipientes a tu espacio personal."
        to="/app/hogar"
        button="Registrar mi hogar"
      />
    );
  async function guardar(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api(form.id ? `/recipientes/${form.id}` : "/recipientes", {
        method: form.id ? "PATCH" : "POST",
        body: data,
      });
      setForm(null);
      state.reload();
      notify("Recipiente guardado.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function archivar(c) {
    if (!window.confirm(`¿Archivar “${c.name}”? Su historial se conservará.`)) return;
    setBusy(true);
    setError("");
    try {
      await api(`/recipientes/${c.id}/archivar`, {
        method: "POST",
      });
      state.reload();
      notify("Recipiente archivado.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <TituloPagina
        eyebrow="CADA LITRO EN SU LUGAR"
        title="Mis reservas"
        text="Controla el agua disponible en tus bidones, tanques y otros recipientes."
        action={
          <button
            className="btn btn-primary"
            onClick={() => {
              setForm({});
              setError("");
            }}
          >
            <Plus size={18} />
            Agregar recipiente
          </button>
        }
      />
      <CajaError message={error} />
      {form && (
        <section className="panel mb-4">
          <div className="panel-heading">
            <h2>{form.id ? "Editar recipiente" : "Nuevo recipiente"}</h2>
            <button
              className="icon-button"
              aria-label="Cerrar formulario"
              onClick={() => setForm(null)}
              disabled={busy}
            >
              <X size={20} />
            </button>
          </div>
          <form onSubmit={guardar} key={form.id || "new"}>
            <div className="form-grid">
              <Campo
                label="Nombre del recipiente"
                name="name"
                required
                minLength={2}
                maxLength={80}
                placeholder="Ej. Tanque del patio"
                defaultValue={form.name}
              />
              {!form.id && (
                <Campo label="Uso del agua">
                  <select
                    className="form-select"
                    name="water_type"
                    defaultValue="drinking"
                  >
                    <option value="drinking">Consumo humano (declarado)</option>
                    <option value="other">Otros usos</option>
                  </select>
                </Campo>
              )}
              <Campo
                label="Capacidad total (L)"
                name="capacity"
                type="number"
                min="0.01"
                max="99999999"
                step="0.01"
                required
                defaultValue={form.capacity}
              />
              {!form.id && (
                <Campo
                  label="Agua disponible al registrarlo (L)"
                  name="initial_balance"
                  type="number"
                  min="0"
                  max="99999999"
                  step="0.01"
                  required
                  defaultValue="0"
                />
              )}
            </div>
            <p className="fine-print">
              El saldo cambia mediante movimientos. Para corregirlo después, registra un
              ajuste con su motivo.
            </p>
            <Enviar busy={busy} />
          </form>
        </section>
      )}
      {state.data.length ? (
        <div className="containers-grid">
          {state.data.map((c) => (
            <article className="container-card" key={c.id}>
              <div className="container-card-top">
                <span className="section-icon">
                  <Cylinder size={23} />
                </span>
                <span
                  className={`badge-soft ${c.water_type === "other" ? "badge-blue" : ""}`}
                >
                  {nombreUsoAgua(c.water_type)}
                </span>
              </div>
              <h2>{c.name}</h2>
              <NivelAgua balance={c.balance} capacity={c.capacity} small />
              <div className="container-numbers">
                <strong>
                  {formatearLitros(c.balance)}
                  <small> L disponibles</small>
                </strong>
                <span>de {formatearLitros(c.capacity)} L de capacidad</span>
              </div>
              <div className="container-actions">
                <Link
                  className="btn btn-light"
                  to={`/app/movimientos?recipiente=${c.id}`}
                >
                  <Plus size={17} />
                  Movimiento
                </Link>
                <button
                  className="icon-button"
                  onClick={() => {
                    setError("");
                    setForm(c);
                    window.scrollTo({
                      top: 0,
                      behavior: "smooth",
                    });
                  }}
                  aria-label={`Editar ${c.name}`}
                >
                  <Pencil size={17} />
                </button>
                <button
                  className="icon-button"
                  disabled={busy}
                  onClick={() => archivar(c)}
                  aria-label={`Archivar ${c.name}`}
                >
                  <Archive size={17} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        !form && (
          <Vacio
            title="Tu primera reserva empieza aquí"
            text="Agrega un recipiente e indica cuánta agua contiene. Puedes empezar con un solo bidón."
          />
        )
      )}
    </>
  );
}
