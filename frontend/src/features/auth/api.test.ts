import { describe, expect, it, vi } from "vitest";

import { mockApi } from "../../test/api";
import { jsonResponse } from "../../test/render";
import { ApiRequestError } from "../../shared/api/http";
import { fetchSession, login, register } from "./api";

describe("API de autenticación", () => {
  it("envía el encabezado CSRF y los datos como JSON", async () => {
    const fetchMock = mockApi({
      "POST /api/auth/register": jsonResponse(201, {
        username: "mechi",
        recovery_code: "ABCD-EFGH-JKMN-PQRS-TVWX",
      }),
    });

    await register("mechi", "mi gato come fideos los martes");

    const [, init] = fetchMock.mock.calls[0] ?? [];
    expect(init?.headers).toMatchObject({ "X-Requested-With": "rinde" });
    expect(init?.body).toBe(
      JSON.stringify({ username: "mechi", password: "mi gato come fideos los martes" }),
    );
  });

  it("convierte el código de error de la API en un error tipado", async () => {
    mockApi({ "POST /api/auth/login": jsonResponse(401, { code: "INVALID_CREDENTIALS" }) });

    await expect(login("mechi", "frase equivocada")).rejects.toMatchObject({
      code: "INVALID_CREDENTIALS",
      status: 401,
    });
  });

  it("trata un cuerpo inesperado como error desconocido", async () => {
    mockApi({ "POST /api/auth/login": new Response("<html>", { status: 502 }) });

    await expect(login("mechi", "x")).rejects.toMatchObject({ code: "UNKNOWN_ERROR" });
  });

  it("informa la falta de conexión", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(login("mechi", "x")).rejects.toBeInstanceOf(ApiRequestError);
    await expect(login("mechi", "x")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });

  it("devuelve null cuando no hay sesión", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }) });

    await expect(fetchSession(new AbortController().signal)).resolves.toBeNull();
  });
});
