import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { House, Info } from "lucide-react";
import {
  useDatos,
  TituloPagina,
  Cargando,
  CajaError,
  Campo,
  Enviar,
} from "../../components/ui";
import { api } from "../../services/api";
import { useAplicacion } from "../../app/context";
export default function Hogar() {
  const { data, loading, error, reload } = useDatos("/hogares/mio");
  const districts = useDatos("/catalogos/distritos");
  const [saveError, setSaveError] = useState(""),
    [busy, setBusy] = useState(false);
  const { notify } = useAplicacion(),
    navigate = useNavigate();
  if (loading || districts.loading) return <Cargando />;
  if (error) return <CajaError message={error} retry={reload} />;
  if (districts.error || !Array.isArray(districts.data) || !districts.data.length)
    return (
      <CajaError
        message={districts.error || "No pudimos cargar la lista de distritos."}
        retry={districts.reload}
      />
    );
  const selectedDistrict = districts.data.includes(data?.district) ? data.district : "";
  const needsDistrictSelection = !!data?.district && !selectedDistrict;
  async function guardar(e) {
    e.preventDefault();
    setBusy(true);
    setSaveError("");
    const f = Object.fromEntries(new FormData(e.currentTarget));
    f.members = Number(f.members);
    f.drinking_daily = f.drinking_daily === "" ? null : f.drinking_daily;
    f.other_daily = f.other_daily === "" ? null : f.other_daily;
    try {
      await api(data ? "/hogares/mio" : "/hogares", {
        method: data ? "PATCH" : "POST",
        body: f,
      });
      notify(
        data
          ? "Datos del hogar actualizados."
          : "Hogar registrado. Ahora agrega tus recipientes.",
      );
      if (!data) navigate("/app/recipientes");
      else reload();
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <TituloPagina
        eyebrow="EL PUNTO DE PARTIDA"
        title="Mi hogar"
        text="Cuéntanos sobre tu hogar para personalizar los cálculos."
      />
      <div className="form-layout">
        <section className="panel">
          <div className="panel-heading">
            <h2>
              <House size={21} />
              Datos del hogar
            </h2>
            <span className="badge-soft">Espacio privado</span>
          </div>
          <CajaError message={saveError} />
          {needsDistrictSelection && (
            <div className="notice notice-warning">
              <p>
                El distrito guardado, «{data.district}», no coincide con la lista.
                Selecciona tu distrito para actualizar el hogar.
              </p>
            </div>
          )}
          <form onSubmit={guardar} key={data?.data_version || "new"}>
            <Campo
              label="Nombre del hogar"
              name="name"
              required
              minLength={2}
              maxLength={80}
              defaultValue={data?.name}
              placeholder="Por ejemplo: Hogar de la familia García"
            />
            <div className="form-grid">
              <Campo
                label="Distrito"
                hint="Provincia de Arequipa · selecciona uno de sus 29 distritos."
              >
                <select
                  className="form-select"
                  name="district"
                  required
                  defaultValue={selectedDistrict}
                >
                  <option value="" disabled>
                    Selecciona tu distrito
                  </option>
                  {districts.data.map((district) => (
                    <option key={district} value={district}>
                      {district}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo
                label="Integrantes"
                name="members"
                type="number"
                min="1"
                max="100"
                step="1"
                required
                defaultValue={data?.members || 1}
              />
            </div>
            <Campo
              label="Sector o zona (opcional)"
              name="sector"
              maxLength={120}
              defaultValue={data?.sector}
              placeholder="Sin incluir tu dirección exacta"
            />
            <div className="form-divider" />
            <h3>Tu estimación de consumo diario</h3>
            <p className="muted">
              Litros por día para todo el hogar. Puedes dejarlos vacíos hasta
              conocerlos.
            </p>
            <div className="form-grid">
              <Campo
                label="Consumo humano declarado (L/día)"
                name="drinking_daily"
                type="number"
                min="0"
                max="99999999"
                step="0.01"
                defaultValue={data?.drinking_daily ?? ""}
                placeholder="Ej. 12"
              />
              <Campo
                label="Otros usos (L/día)"
                name="other_daily"
                type="number"
                min="0"
                max="99999999"
                step="0.01"
                defaultValue={data?.other_daily ?? ""}
                placeholder="Ej. 60"
              />
            </div>
            <div className="notice notice-info">
              <Info size={20} />
              <p>
                Los ejemplos son ilustrativos. No son recomendaciones de consumo ni
                mínimos de salud. Ingresa tu estimación según el uso real de tu hogar.
              </p>
            </div>
            <Enviar busy={busy}>
              {data ? "Actualizar mi hogar" : "Registrar mi hogar"}
            </Enviar>
          </form>
        </section>
        <aside className="help-panel">
          <span className="section-icon">
            <House size={26} />
          </span>
          <h3>Un buen punto de partida</h3>
          <p>
            No necesitas un historial para comenzar. Puedes usar una estimación propia y
            ajustarla al registrar tus consumos.
          </p>
          <div className="form-divider" />
          <h4>¿Qué significa cada uso?</h4>
          <p>
            <strong>Consumo humano:</strong> agua que tú declaras destinada a beber y
            preparar alimentos.
          </p>
          <p>
            <strong>Otros usos:</strong> limpieza, inodoros, riego u otros usos que
            identifiques.
          </p>
          <p className="fine-print">
            La aplicación no determina si el agua es potable.
          </p>
        </aside>
      </div>
    </>
  );
}
