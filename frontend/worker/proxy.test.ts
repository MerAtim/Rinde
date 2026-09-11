// @vitest-environment node
import { describe, expect, it, vi } from "vitest";

import { buildUpstreamUrl, proxyToApi } from "./proxy";

const API_ORIGIN = "https://rinde-api.example.com";

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

    const response = await proxyToApi(new Request("https://rinde.example.dev/api/x"), API_ORIGIN);

    expect(response.headers.get("Cache-Control")).toBe("max-age=60");
  });

  it("responde 502 con un código estable si falta configurar la API", async () => {
    const response = await proxyToApi(new Request("https://rinde.example.dev/api/x"), "");

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ code: "API_ORIGIN_NOT_CONFIGURED" });
  });
});
