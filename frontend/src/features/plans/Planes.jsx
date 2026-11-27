import { useState } from "react";
import {
  Compass,
  Clock3,
  CheckCircle2,
  AlertTriangle,
  Save,
  History,
  Info,
} from "lucide-react";
import {
  useDatos,
  TituloPagina,
  Campo,
  Enviar,
  CajaError,
  Cargando,
  Vacio,
  formatearLitros,
  nombreEstado,
  formatearFecha,
} from "../../components/ui";
import { api } from "../../services/api";
import { useAplicacion } from "../../app/context";
export function ResultadoPlan({ result, historic = false, projected = false }) {
  return (
    <div className="plan-result">
      <div
        className={`result-heading ${result.status === "covered" ? "result-covered" : ""}`}
      >
        {result.status === "covered" ? (
          <CheckCircle2 size={25} />
        ) : (
          <AlertTriangle size={25} />
        )}
        <div>
          <h3>{nombreEstado(result.status)}</h3>
          <p>
            Escenario de {result.hours} horas · {result.reduction_percent}% de reducción
            en otros usos
          </p>
        </div>
      </div>
      <div className="plan-use-grid">
        {result.items.map((i) => (
          <article className="plan-use" key={i.water_type}>
            <span className="eyebrow">
              {i.water_type === "drinking" ? "CONSUMO HUMANO DECLARADO" : "OTROS USOS"}
            </span>
            <strong>
              {formatearLitros(i.deficit)}
              <small> L por cubrir</small>
            </strong>
            <dl>
              <div>
                <dt>
                  Reserva{" "}
                  {projected
                    ? "proyectada al inicio"
                    : historic
                      ? "al guardar"
                      : "actual"}
                </dt>
                <dd>{formatearLitros(i.available)} L</dd>
              </div>
              <div>
                <dt>Necesidad estimada</dt>
                <dd>{formatearLitros(i.required)} L</dd>
              </div>
              <div>
                <dt>Reposición que cabe</dt>
                <dd>{formatearLitros(i.fillable)} L</dd>
              </div>
              <div>
                <dt>Capacidad adicional necesaria</dt>
                <dd>{formatearLitros(i.extra_capacity)} L</dd>
              </div>
            </dl>
            {["unknown", "no_demand"].includes(i.state) && (
              <span className="warning-label">{nombreEstado(i.state)}</span>
            )}
          </article>
        ))}
      </div>
      <div className="action-list">
        <h3>Tu ruta de preparación</h3>
        <ol>
          {result.actions.map((a, i) => (
            <li key={i}>
              <span>{String(i + 1).padStart(2, "0")}</span>
              <p>{a}</p>
            </li>
          ))}
        </ol>
      </div>
      <p className="fine-print">
        {result.basis} Una simulación no modifica tus reservas ni garantiza el
        abastecimiento.
      </p>
    </div>
  );
}
export default function Planes() {
  const home = useDatos("/hogares/mio"),
    history = useDatos("/planes"),
    { notify } = useAplicacion();
  const [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [saving, setSaving] = useState(false),
    [saved, setSaved] = useState(false),
    [selected, setSelected] = useState(null);
  if (home.loading) return <Cargando />;
  if (home.error) return <CajaError message={home.error} retry={home.reload} />;
  if (!home.data)
    return (
      <Vacio
        title="Registra tu hogar para preparar un plan"
        text="Usaremos tus reservas y estimaciones declaradas para calcular un escenario."
        to="/app/hogar"
        button="Registrar mi hogar"
      />
    );
  async function simular(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    setSelected(null);
    setSaved(false);
    const f = Object.fromEntries(new FormData(e.currentTarget));
    try {
      setResult(
        await api("/planes/simular", {
          method: "POST",
          body: {
            hours: Number(f.hours),
            reduction_percent: Number(f.reduction_percent),
          },
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function guardar() {
    setSaving(true);
    setError("");
    try {
      await api("/planes", {
        method: "POST",
        body: {
          hours: result.hours,
          reduction_percent: result.reduction_percent,
          data_version: result.data_version,
        },
      });
      setSaved(true);
      history.reload();
      notify(
        "Plan guardado. Recuerda registrar las recargas cuando realmente ocurran.",
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <TituloPagina
        eyebrow="DE LA INFORMACIÓN A LA ACCIÓN"
        title="Mi plan de contingencia"
        text="Anticipa un corte, compara tus reservas y prepara los siguientes pasos."
      />
      
      <div className="planner-layout">
        <div>
          <section className="panel">
            <div className="panel-heading">
              <h2>
                <Compass size={22} />
                Diseña tu escenario
              </h2>
            </div>
            <form
              onSubmit={simular}
              onChange={() => {
                setResult(null);
                setSaved(false);
              }}
            >
              <div className="form-grid">
                <Campo
                  label="Duración del corte (horas)"
                  name="hours"
                  type="number"
                  min="1"
                  max="720"
                  step="1"
                  defaultValue="48"
                  required
                  hint="Entre 1 hora y 30 días."
                />
                <Campo label="Reducción hipotética en otros usos">
                  <select
                    name="reduction_percent"
                    className="form-select"
                    defaultValue="0"
                  >
                    <option value="0">Sin reducción</option>
                    <option value="10">Reducir 10%</option>
                    <option value="20">Reducir 20%</option>
                    <option value="30">Reducir 30%</option>
                    <option value="50">Reducir 50%</option>
                  </select>
                  <small>No se reduce el consumo humano declarado.</small>
                </Campo>
              </div>
              <Enviar busy={busy}>Simular mi reserva</Enviar>
            </form>
          </section>
          <CajaError message={error} />
          {result && (
            <section className="panel mt-4">
              <ResultadoPlan result={result} />
              <button
                className="btn btn-primary"
                onClick={guardar}
                disabled={saving || saved}
              >
                <Save size={18} />
                {saved ? "Plan guardado" : saving ? "Guardando…" : "Guardar este plan"}
              </button>
            </section>
          )}
          {selected && (
            <section className="panel mt-4">
              <div className="panel-heading">
                <h2>Plan guardado</h2>
                <span className="muted">{formatearFecha(selected.created_at)}</span>
              </div>
              {selected.outdated && (
                <div className="notice notice-warning">
                  <p>
                    Los datos del hogar cambiaron desde este plan. Simula nuevamente
                    para usar los saldos actuales.
                  </p>
                </div>
              )}
              <ResultadoPlan result={selected.snapshot} historic />
            </section>
          )}
          {!result && !selected && (
            <div className="plan-placeholder">
              <Clock3 size={42} />
              <h3>Prepárate con un escenario</h3>
              <p>
                Indica cuántas horas necesitas cubrir y revisa qué acciones puedes
                planificar.
              </p>
            </div>
          )}
        </div>
        <aside className="panel plan-history">
          <div className="panel-heading">
            <h2>
              <History size={20} />
              Mis planes
            </h2>
          </div>
          {history.loading ? (
            <Cargando />
          ) : history.error ? (
            <CajaError message={history.error} retry={history.reload} />
          ) : history.data.length ? (
            history.data.map((p) => (
              <button
                className={`history-item ${selected?.id === p.id ? "history-selected" : ""}`}
                key={p.id}
                onClick={() => {
                  setSelected(p);
                  setResult(null);
                }}
              >
                <strong>Reserva para {p.snapshot.hours} horas</strong>
                <span>{formatearFecha(p.created_at)}</span>
                <small className={p.outdated ? "history-old" : ""}>
                  {p.outdated
                    ? "Datos cambiaron · volver a simular"
                    : nombreEstado(p.snapshot.status)}
                </small>
              </button>
            ))
          ) : (
            <p className="muted">
              Cuando guardes una simulación, aparecerá aquí. Conservamos los datos del
              momento en que la creaste.
            </p>
          )}
        </aside>
      </div>
    </>
  );
}
