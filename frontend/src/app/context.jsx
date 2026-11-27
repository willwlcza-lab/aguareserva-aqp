import { createContext, useContext, useEffect, useState } from "react";
import { api, renovarCsrf, limpiarCsrf } from "../services/api";
const ContextoAplicacion = createContext();
export function ProveedorAplicacion({ children }) {
  const [user, setUser] = useState(null),
    [loading, setLoading] = useState(true),
    [bootError, setBootError] = useState(""),
    [toast, setToast] = useState("");
  async function iniciarAplicacion() {
    setLoading(true);
    setBootError("");
    try {
      await renovarCsrf();
      try {
        setUser(await api("/auth/me"));
      } catch (e) {
        if (e.status !== 401) throw e;
        setUser(null);
      }
    } catch (e) {
      setBootError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    iniciarAplicacion();
    const expired = () => {
      setUser(null);
      setToast("Tu sesión venció. Vuelve a iniciar sesión.");
      renovarCsrf().catch(() => {});
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 6000);
    return () => clearTimeout(id);
  }, [toast]);
  async function cerrarSesion() {
    await api("/auth/logout", {
      method: "POST",
    });
    limpiarCsrf();
    setUser(null);
    await renovarCsrf();
  }
  return (
    <ContextoAplicacion.Provider
      value={{
        user,
        setUser,
        loading,
        bootError,
        boot: iniciarAplicacion,
        logout: cerrarSesion,
        notify: setToast,
      }}
    >
      {children}
      {toast && (
        <div className="toast-message" role="status">
          {toast}
          <button
            type="button"
            aria-label="Cerrar mensaje"
            onClick={() => setToast("")}
          >
            ×
          </button>
        </div>
      )}
    </ContextoAplicacion.Provider>
  );
}
export const useAplicacion = () => useContext(ContextoAplicacion);
