// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import { KEEPALIVE_PATH, pingApi } from "./keepalive";

const API_ORIGIN = "https://rinde-api.example.com";

describe("pingApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("llama al chequeo de vida, sin el secreto de origen", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    await pingApi(API_ORIGIN);

    const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit];
    expect(url.toString()).toBe(`${API_ORIGIN}${KEEPALIVE_PATH}`);
    expect(new Headers(init.headers).has("X-Rinde-Origin")).toBe(false);
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it("falla si la API no responde bien, para que quede en el historial del cron", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));

    await expect(pingApi(API_ORIGIN)).rejects.toThrow("La API respondió 503");
  });

  it("dice cuándo el que frenó el llamado fue el desafío de Render", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Just a moment...", {
          status: 429,
          headers: { "cf-mitigated": "challenge" },
        }),
      ),
    );

    await expect(pingApi(API_ORIGIN)).rejects.toThrow("desafío");
  });

  it("falla sin llamar a nadie si falta configurar la API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(pingApi("")).rejects.toThrow("API_ORIGIN");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
