import assert from "node:assert/strict";
import { afterEach, beforeEach, mock, test } from "node:test";
import { api, ErrorApi, limpiarCsrf, renovarCsrf } from "./api.js";
const jsonResponse = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
beforeEach(() => limpiarCsrf());
afterEach(() => mock.restoreAll());
test("una cuenta sin hogar recibe null sin lanzar un error", async () => {
  mock.method(globalThis, "fetch", async () => jsonResponse(null));
  assert.equal(await api("/hogares/mio"), null);
});
test("el registro del primer hogar conserva el token de la sesión autenticada", async () => {
  const home = {
    name: "Hogar de prueba",
    district: "Cayma",
    members: 4,
  };
  const requests = [];
  mock.method(globalThis, "fetch", async (url, options) => {
    requests.push({
      url,
      options,
    });
    if (url.endsWith("/auth/csrf")) {
      return jsonResponse({
        csrf_token: "token-anonimo-de-prueba",
      });
    }
    if (url.endsWith("/auth/registro")) {
      return jsonResponse({
        user: {
          id: "usuario-de-prueba",
          role: "USER",
        },
        csrf_token: "token-autenticado-de-prueba",
      });
    }
    if (url.endsWith("/hogares/mio")) return jsonResponse(null);
    if (url.endsWith("/hogares")) return jsonResponse(home, 201);
    assert.fail(`Petición inesperada: ${url}`);
  });
  await renovarCsrf();
  await api("/auth/registro", {
    method: "POST",
    body: {
      name: "Usuario de prueba",
      email: "qa@example.com",
    },
  });
  assert.equal(await api("/hogares/mio"), null);
  assert.deepEqual(
    await api("/hogares", {
      method: "POST",
      body: home,
    }),
    home,
  );
  assert.equal(requests[1].options.headers["X-CSRF-Token"], "token-anonimo-de-prueba");
  assert.equal(
    requests[3].options.headers["X-CSRF-Token"],
    "token-autenticado-de-prueba",
  );
  assert.equal(requests[3].options.credentials, "same-origin");
  assert.deepEqual(JSON.parse(requests[3].options.body), home);
});
test("las listas se devuelven sin modificar su contenido", async () => {
  const districts = ["Cayma", "Cerro Colorado"];
  mock.method(globalThis, "fetch", async () => jsonResponse(districts));
  assert.deepEqual(await api("/catalogos/distritos"), districts);
});
test("un error HTTP con respuesta null conserva el código y un mensaje útil", async () => {
  mock.method(globalThis, "fetch", async () => jsonResponse(null, 500));
  await assert.rejects(api("/hogares/mio"), (error) => {
    assert.ok(error instanceof ErrorApi);
    assert.equal(error.status, 500);
    assert.equal(error.message, "No se pudo completar la operación.");
    return true;
  });
});
test("los mensajes de validación del servidor se conservan", async () => {
  mock.method(globalThis, "fetch", async () =>
    jsonResponse(
      {
        detail: "Ya tienes un hogar registrado.",
      },
      409,
    ),
  );
  await assert.rejects(
    api("/hogares", {
      method: "POST",
      body: {},
    }),
    (error) => {
      assert.ok(error instanceof ErrorApi);
      assert.equal(error.status, 409);
      assert.equal(error.message, "Ya tienes un hogar registrado.");
      return true;
    },
  );
});
