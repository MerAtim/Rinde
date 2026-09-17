import { vi } from "vitest";

import { jsonResponse } from "./render";

/** Una respuesta fija, o una función; si devuelve una promesa, sirve para probar lo que pasa mientras se espera. */
type Reply = Response | ((init: RequestInit | undefined) => Response | Promise<Response>);

function pathOf(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  return input instanceof URL ? input.pathname : input.url;
}

/**
 * API falsa para tests de pantallas: responde según "MÉTODO /ruta".
 * El estado del sistema siempre responde "operativo" salvo que el test diga otra cosa.
 */
export function mockApi(routes: Record<string, Reply>) {
  const table: Record<string, Reply> = {
    "GET /api/health/ready": jsonResponse(200, { status: "ok", database: "ok" }),
    ...routes,
  };
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const reply = table[`${init?.method ?? "GET"} ${pathOf(input)}`];
    if (reply === undefined) {
      return Promise.resolve(jsonResponse(404, { code: "NOT_FOUND" }));
    }
    return Promise.resolve(typeof reply === "function" ? reply(init) : reply.clone());
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
