import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Waves,
  MapPin,
  RefreshCw,
  ExternalLink,
  Bell,
  ShieldCheck,
} from "lucide-react";
import { api } from "../../services/api";
import { useAplicacion } from "../../app/context";
import {
  useDatos,
  TituloPagina,
  CajaError,
  Cargando,
  Vacio,
  Campo,
  formatearFecha,
} from "../../components/ui";
import { ResultadoPlan } from "../plans/Planes";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
const etiquetas = {
  automatico: "Extraído de fuente oficial",
  pendiente: "Pendiente de revisión",
  aprobado: "Revisado localmente",
  historico: "Referencia histórica",
  plazo_estimado_pasado: "Terminó el plazo estimado · sin confirmación",
  programado: "Anunciado a futuro",
  en_horario_anunciado: "Dentro del horario anunciado",
  anunciado_hoy_sin_confirmar: "Anunciado para hoy · confirmar atención",
  anunciado_futuro: "Reparto anunciado a futuro",
  horario_desconocido: "Horario incompleto",
  consultada: "Consulta completada",
  sin_consultar: "Aún sin consultar",
  desactualizada: "Actualización pendiente",
  error_o_parcial: "Consulta incompleta o con error",
};
const mostrarFecha = (valor) =>
  valor ? formatearFecha(valor) : "No indicada por la fuente";
function Procedencia({ registro }) {
  return (
    <div className="procedencia">
      <span>
        {registro.fuente.nombre} ·{" "}
        {registro.fuente.tipo === "oficial"
          ? "Fuente oficial"
          : registro.fuente.tipo === "ong"
            ? "ONG"
            : "Sitio no oficial"}
      </span>
      <a href={registro.datos.url} target="_blank" rel="noreferrer">
        Consultar publicación <ExternalLink size={13} />
      </a>
      <small>
        Consulta: {mostrarFecha(registro.consultado)} · Publicación:{" "}
        {mostrarFecha(registro.datos.publicado)}
      </small>
      {registro.fuente_desactualizada && (
        <strong className="text-warning-emphasis">
          La fuente necesita actualizarse; se conservan los últimos datos.
        </strong>
      )}
    </div>
  );
}
function EvaluacionAviso({ aviso }) {
  const [horas, setHoras] = useState(""),
    [resultado, setResultado] = useState(null),
    [error, setError] = useState(""),
    [ocupado, setOcupado] = useState(false),
    [guardado, setGuardado] = useState(false);
  const { notify } = useAplicacion();
  async function evaluar(evento) {
    evento.preventDefault();
    setOcupado(true);
    setError("");
    setResultado(null);
    setGuardado(false);
    try {
      setResultado(
        await api(`/publicaciones/${aviso.id}/evaluar`, {
          method: "POST",
          body: {
            horas_manuales: horas ? Number(horas) : null,
          },
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }
  async function guardar() {
    setOcupado(true);
    setError("");
    try {
      await api(`/publicaciones/${aviso.id}/guardar-plan`, {
        method: "POST",
        body: {
          horas_manuales: resultado.manual ? resultado.horas : null,
          version_datos: resultado.actual.data_version,
        },
      });
      setGuardado(true);
      notify("Plan guardado. Tus saldos no cambiaron.");
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }
  return (
    <details className="evaluacion-aviso">
      <summary>Evaluar mis reservas ante este aviso</summary>
      <p>
        Se usan los consumos diarios declarados de tu hogar. Una coincidencia de
        distrito no confirma que tu vivienda esté afectada.
      </p>
      <form onSubmit={evaluar} className="filtros-fuentes">
        <Campo
          label="Horas de escenario manual (opcional)"
          hint="Déjalo vacío para usar el horario anunciado; es necesario si el aviso es histórico o está incompleto."
        >
          <input
            className="form-control"
            type="number"
            min="1"
            max="720"
            value={horas}
            onChange={(e) => {
              setHoras(e.target.value);
              setResultado(null);
            }}
            placeholder="Ejemplo: 24"
          />
        </Campo>
        <button className="btn btn-primary" disabled={ocupado}>
          Calcular preparación
        </button>
      </form>
      <CajaError message={error} />
      {resultado && (
        <div className="resultado-aviso">
          <div className="notice notice-info">
            <p>
              {resultado.supuesto} {resultado.advertencia}
            </p>
          </div>
          {resultado.fuente_pendiente && (
            <p className="warning-label">
              Este aviso complementario sigue pendiente de revisión. Confirma la fuente.
            </p>
          )}
          <h3>Escenario con la reserva actual</h3>
          <ResultadoPlan result={resultado.actual} />
          {resultado.proyeccion_inicio && (
            <>
              <h3>Reserva proyectada al inicio del corte</h3>
              <p>
                Faltan aproximadamente {resultado.horas_hasta_inicio} horas para el
                inicio anunciado.
              </p>
              <ResultadoPlan result={resultado.proyeccion_inicio} projected />
              {resultado.agotamiento_antes && (
                <p className="warning-label">
                  Con el consumo declarado, algún tipo de reserva podría agotarse antes
                  de empezar el corte.
                </p>
              )}
            </>
          )}
          <div className="d-flex flex-wrap gap-3">
            <button
              className="btn btn-primary"
              disabled={ocupado || guardado}
              onClick={guardar}
            >
              {guardado ? "Plan guardado" : "Guardar este plan"}
            </button>
            <Link
              className="btn btn-outline-primary"
              to={`/app/abastecimiento?distrito=${encodeURIComponent(aviso.datos.distritos?.[0] || "")}`}
            >
              Consultar abastecimiento
            </Link>
          </div>
        </div>
      )}
    </details>
  );
}
export function AlertasPersonales() {
  const { data, error, reload } = useDatos("/alertas");
  const { notify } = useAplicacion();
  if (error) return <CajaError message={error} retry={reload} />;
  const pendientes = (data || []).filter(
    (a) => !a.leida && ["programado", "en_horario_anunciado"].includes(a.vigencia),
  );
  if (!pendientes.length) return null;
  async function leer(id) {
    try {
      await api(`/alertas/${id}/leer`, {
        method: "POST",
      });
      reload();
    } catch (e) {
      notify(e.message);
    }
  }
  return (
    <section className="notice notice-info alertas-hogar">
      <Bell size={24} />
      <div>
        <strong>Avisos para revisar en tu distrito</strong>
        {pendientes.map((a) => (
          <p key={a.id}>
            {a.titulo} <Link to="/app/cortes">Ver cortes</Link>{" "}
            <button className="text-button" onClick={() => leer(a.id)}>
              Marcar leído
            </button>
          </p>
        ))}
      </div>
    </section>
  );
}
export function Cortes() {
  const [distrito, setDistrito] = useState(""),
    [propios, setPropios] = useState(true),
    [historicos, setHistoricos] = useState(false),
    [pagina, setPagina] = useState(0);
  const catalogo = useDatos("/catalogos/distritos");
  const { data, loading, error, reload } = useDatos(
    `/publicaciones?categoria=corte&distrito=${encodeURIComponent(distrito)}&solo_mi_hogar=${propios}&historicos=${historicos}&limite=30&desplazamiento=${pagina * 30}`,
  );
  return (
    <>
      <TituloPagina
        eyebrow="OBSERVATORIO DEL AGUA"
        title="Avisos y preparación"
        text="Relaciona los avisos publicados con las reservas de tu hogar. Horarios de Arequipa (UTC−5)."
      />
      <AlertasPersonales />
      <div className="notice notice-info">
        <Waves size={24} />
        <p>
          La consulta automática detecta publicaciones, no mide el suministro de tu
          vivienda. Una hora estimada de reposición no confirma el retorno del agua.{" "}
          <Link to="/app/fuentes">Ver estado de las fuentes</Link>
        </p>
      </div>
      <div className="panel filtros-fuentes">
        <Campo label="Distrito">
          <select
            className="form-select"
            value={distrito}
            disabled={propios}
            onChange={(e) => {
              setDistrito(e.target.value);
              setPagina(0);
            }}
          >
            <option value="">Todos los distritos</option>
            {(catalogo.data || []).map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </Campo>
        <label>
          <input
            type="checkbox"
            checked={propios}
            onChange={(e) => {
              setPropios(e.target.checked);
              setPagina(0);
            }}
          />{" "}
          Solo mi hogar
        </label>
        <label>
          <input
            type="checkbox"
            checked={historicos}
            onChange={(e) => {
              setHistoricos(e.target.checked);
              setPagina(0);
            }}
          />{" "}
          Incluir históricos
        </label>
        <button className="btn btn-outline-primary" onClick={reload}>
          <RefreshCw size={16} /> Actualizar vista
        </button>
      </div>
      {loading ? (
        <Cargando />
      ) : error ? (
        <CajaError message={error} retry={reload} />
      ) : (
        <>
          <p className="muted">
            {data.total || 0} avisos con estos filtros. La ausencia de avisos no
            garantiza continuidad del servicio.
          </p>
          {!data.registros.length && (
            <Vacio
              title="No hay avisos para estos filtros"
              text={
                data.mensaje ||
                "Revisa las fuentes o activa los históricos para una demostración con fechas reales."
              }
              to="/app/fuentes"
              button="Ver fuentes"
            />
          )}
          <div className="lista-avisos">
            {data.registros.map((a) => (
              <article key={a.id} className="panel tarjeta-aviso">
                <div className="etiquetas">
                  <span
                    className={`etiqueta ${a.fuente.tipo === "oficial" ? "oficial" : "complementaria"}`}
                  >
                    {a.fuente.tipo === "oficial"
                      ? "SEDAPAR · OFICIAL"
                      : "FUENTE COMPLEMENTARIA"}
                  </span>
                  <span className="etiqueta">
                    {etiquetas[a.vigencia] || a.vigencia}
                  </span>
                </div>
                <h2>{a.datos.titulo}</h2>
                <p className="distritos-aviso">
                  <MapPin size={16} /> {a.datos.distritos.join(" · ")}
                </p>
                <dl className="horario-aviso">
                  <div>
                    <dt>Inicio anunciado</dt>
                    <dd>{mostrarFecha(a.datos.inicio)}</dd>
                  </div>
                  <div>
                    <dt>Reposición estimada</dt>
                    <dd>{mostrarFecha(a.datos.fin_estimado)}</dd>
                  </div>
                </dl>
                {a.coincidencia && <p className="coincidencia">{a.coincidencia}</p>}
                <details>
                  <summary>Zonas y circuito anunciados</summary>
                  <p>{a.datos.zonas || "La fuente no detalla zonas."}</p>
                  <p>Circuitos: {a.datos.circuitos || "No indicados"}</p>
                  <p>{a.observacion}</p>
                </details>
                <Procedencia registro={a} />
                <EvaluacionAviso aviso={a} />
              </article>
            ))}
          </div>
          <div className="d-flex gap-3">
            <button
              disabled={!pagina}
              className="btn btn-outline-primary"
              onClick={() => setPagina((p) => p - 1)}
            >
              Anterior
            </button>
            <button
              disabled={!data.hay_mas}
              className="btn btn-outline-primary"
              onClick={() => setPagina((p) => p + 1)}
            >
              Siguiente
            </button>
          </div>
        </>
      )}
    </>
  );
}
export function MapaPuntos({ puntos }) {
  const elemento = useRef(null);
  const [errorFondo, setErrorFondo] = useState(false);
  const ubicados = puntos.filter(
    (p) =>
      p.datos.coordenadas_verificadas &&
      p.datos.latitud != null &&
      p.datos.longitud != null,
  );
  const clave = JSON.stringify(
    ubicados.map((p) => [
      p.id,
      p.datos.latitud,
      p.datos.longitud,
      p.datos.titulo,
      p.vigencia,
    ]),
  );
  useEffect(() => {
    if (!elemento.current || !ubicados.length) return;
    setErrorFondo(false);
    const mapa = L.map(elemento.current, {
      scrollWheelZoom: false,
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    })
      .on("tileerror", () => setErrorFondo(true))
      .addTo(mapa);
    const limites = [];
    ubicados.forEach((p) => {
      const posicion = [p.datos.latitud, p.datos.longitud];
      limites.push(posicion);
      const contenido = document.createElement("div");
      contenido.textContent = `${p.datos.titulo} · ${etiquetas[p.vigencia] || p.vigencia}`;
      L.circleMarker(posicion, {
        radius: 9,
        color: "#007f91",
        fillOpacity: 0.8,
      })
        .addTo(mapa)
        .bindPopup(contenido);
    });
    mapa.fitBounds(limites, {
      padding: [35, 35],
      maxZoom: 15,
    });
    return () => mapa.remove();
  }, [clave]);
  if (!ubicados.length)
    return (
      <div className="notice notice-info">
        <MapPin size={23} />
        <p>
          Estos avisos no incluyen coordenadas verificadas. Consulta las direcciones de
          la lista. El mapa mostrará únicamente ubicaciones respaldadas y revisadas.
        </p>
      </div>
    );
  return (
    <>
      {errorFondo && (
        <div className="notice notice-info">
          <p>
            No se pudo cargar el fondo del mapa. Los puntos y las direcciones siguen
            disponibles; revisa tu conexión.
          </p>
        </div>
      )}
      <div
        ref={elemento}
        className="mapa-puntos"
        role="region"
        aria-label="Mapa de puntos con ubicación verificada"
      />
      <p className="fine-print">
        La ubicación no confirma disponibilidad de agua. Consulta fecha, horario y
        fuente de cada punto. El fondo del mapa necesita Internet.
      </p>
    </>
  );
}
export function Abastecimiento() {
  const [distrito, setDistrito] = useState(
      () => new URLSearchParams(window.location.search).get("distrito") || "",
    ),
    [historicos, setHistoricos] = useState(false);
  const catalogo = useDatos("/catalogos/distritos");
  const { data, loading, error, reload } = useDatos(
    `/publicaciones?categoria=punto&distrito=${encodeURIComponent(distrito)}&historicos=${historicos}&limite=200`,
  );
  return (
    <>
      <TituloPagina
        eyebrow="ABASTECIMIENTO DOCUMENTADO"
        title="Dónde se anuncia reparto"
        text="Puntos publicados de distribución por cisternas. Confirma el recorrido y la atención antes de desplazarte."
      />
      <div className="panel filtros-fuentes">
        <Campo label="Distrito">
          <select
            className="form-select"
            value={distrito}
            onChange={(e) => setDistrito(e.target.value)}
          >
            <option value="">Todos los distritos</option>
            {(catalogo.data || []).map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </Campo>
        <label>
          <input
            type="checkbox"
            checked={historicos}
            onChange={(e) => setHistoricos(e.target.checked)}
          />{" "}
          Incluir históricos
        </label>
        <button className="btn btn-outline-primary" onClick={reload}>
          Actualizar vista
        </button>
      </div>
      <p className="fine-print">
        Los registros de Cortedeagua.net.pe son complementarios y no incluyen el enlace
        individual al comunicado oficial. No se presentan como centros permanentes ni
        como atención confirmada. <Link to="/app/fuentes">Consultar fuentes</Link>
      </p>
      {loading ? (
        <Cargando />
      ) : error ? (
        <CajaError message={error} retry={reload} />
      ) : (
        <>
          <MapaPuntos puntos={data.registros} />
          {!data.registros.length && (
            <Vacio
              title="Sin puntos publicados para este filtro"
              text="Esto no significa que no exista abastecimiento. Revisa la fecha de consulta y los canales de Sedapar."
            />
          )}
          <div className="rejilla-puntos">
            {data.registros.map((p) => (
              <article className="panel tarjeta-punto" key={p.id}>
                <span className="etiqueta">{etiquetas[p.vigencia] || p.vigencia}</span>
                <h2>
                  <MapPin size={20} /> {p.datos.titulo}
                </h2>
                <p>{p.datos.distritos.join(" · ")}</p>
                <p>
                  <strong>Fecha de reparto:</strong> {p.datos.fecha_atencion}
                  <br />
                  <strong>Hora aproximada:</strong> {p.datos.horario}
                </p>
                <p>{p.observacion}</p>
                <Procedencia registro={p} />
                {p.datos.procedencia_coordenadas && (
                  <a
                    href={p.datos.procedencia_coordenadas}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Referencia de ubicación
                  </a>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </>
  );
}
export function Fuentes() {
  const fuentes = useDatos("/fuentes"),
    recursos = useDatos("/publicaciones?categoria=orientacion");
  return (
    <>
      <TituloPagina
        eyebrow="TRANSPARENCIA"
        title="De dónde vienen los datos"
        text="La fecha de consulta no es la fecha del hecho. Todas las consultas necesitan Internet y el sincronizador en ejecución."
      />
      {fuentes.loading ? (
        <Cargando />
      ) : fuentes.error ? (
        <CajaError message={fuentes.error} retry={fuentes.reload} />
      ) : (
        <div className="rejilla-puntos">
          {fuentes.data.map((f) => (
            <article className="panel" key={f.clave}>
              <ShieldCheck size={24} />
              <h2>{f.nombre}</h2>
              <span className="etiqueta">{etiquetas[f.estado]}</span>
              <p>
                {f.tipo === "oficial"
                  ? "Organismo oficial"
                  : f.tipo === "ong"
                    ? "Organización no gubernamental"
                    : "Sitio complementario no oficial"}
              </p>
              <p>
                Último intento: {mostrarFecha(f.ultimo_intento)}
                <br />
                Último éxito: {mostrarFecha(f.ultimo_exito)}
                <br />
                Intervalo configurado: {f.intervalo_minutos} minutos
              </p>
              <a href={f.url} target="_blank" rel="noreferrer">
                Abrir fuente original
              </a>
            </article>
          ))}
        </div>
      )}
      <h2 className="mt-4">Agua y comunidad · ONG</h2>
      <p>Material general de orientación; separado de los avisos operativos locales.</p>
      {recursos.error && <CajaError message={recursos.error} retry={recursos.reload} />}
      {recursos.data?.registros.map((r) => (
        <article className="panel" key={r.id}>
          <h3>{r.datos.titulo}</h3>
          <p>{r.datos.resumen}</p>
          <p>{r.datos.alcance}</p>
          <Procedencia registro={r} />
        </article>
      ))}
      {!recursos.loading && !recursos.data?.registros.length && (
        <p>
          Aún no hay contenido de ONG recuperado. Consulta el estado de Manos Unidas.
        </p>
      )}
      <div className="notice notice-info mt-4">
        <p>
          El directorio de acopio de Sedapar de 2024 es una referencia histórica y no se
          carga como puntos activos.{" "}
          <a
            href="https://www.gob.pe/institucion/sedapar/informes-publicaciones/5198948-directorio-de-puntos-de-acopio-de-agua-potable-arequipa"
            target="_blank"
            rel="noreferrer"
          >
            Consultar directorio histórico
          </a>
          .
        </p>
      </div>
    </>
  );
}
function RevisarRegistro({ registro, alTerminar }) {
  const [ocupado, setOcupado] = useState(false),
    [error, setError] = useState("");
  async function revisar(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setOcupado(true);
    setError("");
    try {
      await api(`/admin/fuentes/publicaciones/${registro.id}`, {
        method: "PATCH",
        body: {
          estado: f.get("estado"),
          nota: f.get("nota"),
          latitud: f.get("latitud") ? Number(f.get("latitud")) : null,
          longitud: f.get("longitud") ? Number(f.get("longitud")) : null,
          referencia_coordenadas: f.get("referencia") || null,
        },
      });
      alTerminar();
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }
  return (
    <article className="panel">
      <div className="etiquetas">
        <span className="etiqueta">{registro.categoria}</span>
        <span className="etiqueta">{etiquetas[registro.vigencia]}</span>
      </div>
      <h3>{registro.datos.titulo}</h3>
      <p>{registro.datos.distritos?.join(" · ")}</p>
      <p>{registro.observacion}</p>
      <Procedencia registro={registro} />
      <details>
        <summary>Revisar este registro</summary>
        <p>
          Comprueba el comunicado y deja evidencia. Aprobar aquí no convierte el
          recopilador en una fuente oficial.
        </p>
        <form onSubmit={revisar}>
          <Campo label="Decisión">
            <select name="estado" className="form-select">
              <option value="aprobado">Aprobar revisión local</option>
              <option value="descartado">Descartar</option>
            </select>
          </Campo>
          <Campo label="Nota de revisión y evidencia">
            <textarea
              name="nota"
              className="form-control"
              required
              minLength={10}
              maxLength={1000}
            />
          </Campo>
          {registro.categoria === "punto" && (
            <>
              <p>Ubicación opcional: completa solamente si la comprobaste.</p>
              <div className="row">
                <div className="col">
                  <Campo label="Latitud">
                    <input
                      className="form-control"
                      name="latitud"
                      type="number"
                      step="any"
                      min="-90"
                      max="90"
                    />
                  </Campo>
                </div>
                <div className="col">
                  <Campo label="Longitud">
                    <input
                      className="form-control"
                      name="longitud"
                      type="number"
                      step="any"
                      min="-180"
                      max="180"
                    />
                  </Campo>
                </div>
              </div>
              <Campo label="Enlace HTTPS que respalda las coordenadas">
                <input className="form-control" name="referencia" type="url" />
              </Campo>
            </>
          )}
          <CajaError message={error} />
          <button className="btn btn-primary" disabled={ocupado}>
            Guardar revisión
          </button>
        </form>
      </details>
    </article>
  );
}
export function FuentesAdmin() {
  const [pagina, setPagina] = useState(0),
    [ocupado, setOcupado] = useState(false),
    [error, setError] = useState("");
  const historial = useDatos("/admin/fuentes/historial"),
    revision = useDatos(
      `/admin/fuentes/revision?limite=15&desplazamiento=${pagina * 15}`,
    );
  const { notify } = useAplicacion();
  // El navegador solo vuelve a leer estados; el proceso Python realiza la sincronización.
  useEffect(() => {
    const id = setInterval(() => historial.reload(), 15000);
    return () => clearInterval(id);
  }, []);
  async function sincronizar() {
    setOcupado(true);
    setError("");
    try {
      const r = await api("/admin/fuentes/sincronizar", {
        method: "POST",
      });
      notify(r.mensaje);
      historial.reload();
      revision.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }
  return (
    <>
      <TituloPagina
        eyebrow="ADMINISTRACIÓN"
        title="Fuentes y revisión"
        text="Consulta los resultados del sincronizador y revisa registros ambiguos."
        action={
          <button className="btn btn-primary" disabled={ocupado} onClick={sincronizar}>
            <RefreshCw size={17} /> Sincronizar ahora
          </button>
        }
      />
      <CajaError message={error} />
      <p>
        El arranque automático se realiza con ABRIR_SINCRONIZADOR.cmd.{" "}
        <Link to="/app/fuentes">Ver última consulta de cada fuente</Link>.
      </p>
      <section className="panel">
        <h2>Historial de consultas</h2>
        {historial.error ? (
          <CajaError message={historial.error} retry={historial.reload} />
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Fuente</th>
                  <th>Inicio</th>
                  <th>Estado</th>
                  <th>Nuevos</th>
                  <th>Actualizados</th>
                  <th>Detalle</th>
                </tr>
              </thead>
              <tbody>
                {historial.data?.map((e) => (
                  <tr key={e.id}>
                    <td>{e.fuente_clave}</td>
                    <td>{mostrarFecha(e.iniciado)}</td>
                    <td>{e.estado}</td>
                    <td>{e.nuevos}</td>
                    <td>{e.actualizados}</td>
                    <td className="detalle-error">{e.detalle || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <div className="d-flex justify-content-between align-items-center my-4">
        <h2>Pendientes de revisión</h2>
        <button className="btn btn-outline-primary" onClick={revision.reload}>
          Actualizar pendientes
        </button>
      </div>
      {revision.loading ? (
        <Cargando />
      ) : revision.error ? (
        <CajaError message={revision.error} retry={revision.reload} />
      ) : (
        <>
          {revision.data.registros.map((r) => (
            <RevisarRegistro key={r.id} registro={r} alTerminar={revision.reload} />
          ))}
          {!revision.data.registros.length && <p>No hay pendientes en esta página.</p>}
          <div className="d-flex gap-3">
            <button
              className="btn btn-outline-primary"
              disabled={!pagina}
              onClick={() => setPagina((p) => p - 1)}
            >
              Anterior
            </button>
            <button
              className="btn btn-outline-primary"
              disabled={!revision.data.hay_mas}
              onClick={() => setPagina((p) => p + 1)}
            >
              Siguiente
            </button>
          </div>
        </>
      )}
    </>
  );
}
