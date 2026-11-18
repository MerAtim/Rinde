// @vitest-environment node
import { describe, expect, it, vi } from "vitest";

import { buildUpstreamUrl, ORIGIN_SECRET_HEADER, proxyToApi } from "./proxy";

const API_ORIGIN = "https://rinde-api.example.com";
const SECRET = "x".repeat(40);

describe("buildUpstreamUrl", () => {
  it("traslada ruta y query al origen de la API, sin conservar el host entrante", () => {
    const url = buildUpstreamUrl("https://rinde.example.dev/api/health/ready?x=1", API_ORIGIN);

    expect(url.toString()).toBe("https://rinde-api.example.com/api/health/ready?x=1");
  });
});

describe("proxyToApi", () => {
  it("reenvía el pedido y agrega cabeceras de seguridad", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ status: "ok" }, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await proxyToApi(
      new Request("https://rinde.example.dev/api/health/live"),
      API_ORIGIN,
      SECRET,
    );

    const forwarded = fetchMock.mock.calls[0]?.[0] as Request;
    expect(forwarded.url).toBe("https://rinde-api.example.com/api/health/live");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(response.headers.get("X-Content-Type-Options")).toBe("nosniff");
  });

  it("respeta las cabeceras que ya define la API", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(null, { status: 204, headers: { "Cache-Control": "max-age=60" } }),
        ),
    );

    const response = await proxyToApi(
      new Request("https://rinde.example.dev/api/x"),
      API_ORIGIN,
      SECRET,
    );

    expect(response.headers.get("Cache-Control")).toBe("max-age=60");
  });

  it("responde 502 con un código estable si falta configurar la API", async () => {
    const response = await proxyToApi(new Request("https://rinde.example.dev/api/x"), "", SECRET);

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ code: "API_ORIGIN_NOT_CONFIGURED" });
  });

  it("le manda a la API el secreto de origen, y pisa el que mande el visitante", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await proxyToApi(
      new Request("https://rinde.example.dev/api/accounts", {
        headers: { [ORIGIN_SECRET_HEADER]: "inventado" },
      }),
      API_ORIGIN,
      SECRET,
    );

    const forwarded = fetchMock.mock.calls[0]?.[0] as Request;
    expect(forwarded.headers.get(ORIGIN_SECRET_HEADER)).toBe(SECRET);
  });

  it("sin secreto no reenvía nada y dice qué falta configurar", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await proxyToApi(
      new Request("https://rinde.example.dev/api/x"),
      API_ORIGIN,
      "",
    );

    expect(fetchMock).not.toHaveBeenCalled();
    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ code: "ORIGIN_SECRET_NOT_CONFIGURED" });
  });
});
