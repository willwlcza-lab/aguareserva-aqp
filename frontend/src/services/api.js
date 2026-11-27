let csrfToken = "";
const BASE = "/api/v1";
export class ErrorApi extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}
export async function api(path, { method = "GET", body, ...rest } = {}) {
  const headers = {
    ...(body
      ? {
          "Content-Type": "application/json",
        }
      : {}),
    ...(method !== "GET"
      ? {
          "X-CSRF-Token": csrfToken,
        }
      : {}),
  };
  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      credentials: "same-origin",
      headers,
      ...(body
        ? {
            body: JSON.stringify(body),
          }
        : {}),
      ...rest,
    });
  } catch {
    throw new ErrorApi(
      "No pudimos conectar con el servidor. Revisa tu conexión e inténtalo otra vez.",
      0,
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login" && path !== "/auth/me")
      window.dispatchEvent(new Event("session-expired"));
    throw new ErrorApi(
      typeof data?.detail === "string"
        ? data.detail
        : "No se pudo completar la operación.",
      response.status,
    );
  }
  if (data?.csrf_token) csrfToken = data.csrf_token;
  return data;
}
export async function renovarCsrf() {
  return api("/auth/csrf");
}
export function limpiarCsrf() {
  csrfToken = "";
}
