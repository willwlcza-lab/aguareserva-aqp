import { useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, ArrowDownUp } from "lucide-react";
import { api } from "../../services/api";
import { useAplicacion } from "../../app/context";
import {
  useDatos,
  TituloPagina,
  Cargando,
  CajaError,
  Vacio,
  Campo,
  Enviar,
  TablaMovimientos,
  formatearLitros,
  nombreUsoAgua,
} from "../../components/ui";
export default function Movimientos() {
  const [page, setPage] = useState(0),
    rows = useDatos(`/movimientos?limit=20&offset=${page * 20}`),
    containers = useDatos("/recipientes");
  const [search] = useSearchParams(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [kind, setKind] = useState("consumption");
  const key = useRef(crypto.randomUUID()),
    { notify } = useAplicacion();
  if (containers.loading) return <Cargando />;
  if (containers.error)
    return <CajaError message={containers.error} retry={containers.reload} />;
  async function guardar(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const form = e.currentTarget,
      data = Object.fromEntries(new FormData(form)),
      id = data.container_id;
    delete data.container_id;
    data.idempotency_key = key.current;
    try {
      await api(`/recipientes/${id}/movimientos`, {
        method: "POST",
        body: data,
      });
      key.current = crypto.randomUUID();
      form.elements.liters.value = "";
      form.elements.reason.value = "";
      rows.reload();
      containers.reload();
      notify("Movimiento registrado. La reserva se actualizó.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <TituloPagina
        eyebrow="UN REGISTRO, MÁS CLARIDAD"
        title="Movimientos de agua"
        text="Registra cada recarga, consumo o corrección de tu reserva."
        action={
          containers.data.length > 0 && (
            <a
              className="btn btn-outline-secondary"
              href="/api/v1/reportes/movimientos.csv"
              download
            >
              <Download size={18} />
              Descargar CSV
            </a>
          )
        }
      />
      {!containers.data.length ? (
        <Vacio
          title="Agrega un recipiente para empezar"
          text="Los movimientos se registran sobre una reserva de tu hogar."
          to="/app/recipientes"
          button="Ir a mis reservas"
        />
      ) : (
        <section className="panel mb-4">
          <div className="panel-heading">
            <h2>
              <ArrowDownUp size={21} />
              Registrar movimiento
            </h2>
            <span className="badge-soft">Litros · L</span>
          </div>
          <CajaError message={error} />
          <form
            onSubmit={guardar}
            onChange={() => {
              key.current = crypto.randomUUID();
            }}
          >
            <div className="form-grid three">
              <Campo label="Recipiente">
                <select
                  className="form-select"
                  name="container_id"
                  defaultValue={search.get("recipiente") || containers.data[0].id}
                >
                  {containers.data.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} · {formatearLitros(c.balance)} L ·{" "}
                      {nombreUsoAgua(c.water_type)}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo label="Tipo de movimiento">
                <select
                  className="form-select"
                  name="kind"
                  value={kind}
                  onChange={(e) => setKind(e.target.value)}
                >
                  <option value="consumption">Consumo (salida)</option>
                  <option value="refill">Recarga (entrada)</option>
                  <option value="adjust_up">Ajuste de entrada</option>
                  <option value="adjust_down">Ajuste de salida</option>
                </select>
              </Campo>
              <Campo
                label="Cantidad (L)"
                name="liters"
                type="number"
                min="0.01"
                max="99999999"
                step="0.01"
                required
                placeholder="Ej. 5"
              />
            </div>
            <Campo
              label={
                kind.startsWith("adjust")
                  ? "Motivo del ajuste (obligatorio)"
                  : "Nota (opcional)"
              }
              name="reason"
              required={kind.startsWith("adjust")}
              minLength={kind.startsWith("adjust") ? 5 : undefined}
              maxLength={240}
              placeholder={
                kind.startsWith("adjust")
                  ? "Explica por qué corriges la reserva"
                  : "Ej. Limpieza del hogar"
              }
            />
            <Enviar busy={busy}>Registrar movimiento</Enviar>
          </form>
        </section>
      )}
      <section className="panel">
        <div className="panel-heading">
          <h2>Historial de movimientos</h2>
          <span className="muted">Más recientes primero</span>
        </div>
        {rows.loading ? (
          <Cargando />
        ) : rows.error ? (
          <CajaError message={rows.error} retry={rows.reload} />
        ) : (
          <>
            <TablaMovimientos rows={rows.data} />
            <div className="pagination-row">
              <button
                className="btn btn-light"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                Anterior
              </button>
              <span>Página {page + 1}</span>
              <button
                className="btn btn-light"
                disabled={rows.data.length < 20}
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
