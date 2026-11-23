import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { ApiRequestError } from "../../shared/api/http";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { RequireSession } from "./SessionRoutes";
import { retryWhileWaking, WAKE_MAX_RETRIES, wakeRetryDelay } from "./useSession";

describe("retryWhileWaking", () => {
  it("espera mientras la API despierta o no hay red", () => {
    expect(retryWhileWaking(0, new ApiRequestError("API_UNAVAILABLE", 503))).toBe(true);
    expect(retryWhileWaking(0, new ApiRequestError("API_UNREACHABLE", 502))).toBe(true);
    expect(retryWhileWaking(0, new ApiRequestError("UNKNOWN_ERROR", 504))).toBe(true);
    expect(retryWhileWaking(0, new ApiRequestError("NETWORK_ERROR", 0))).toBe(true);
  });

  it("no insiste con un error que no se arregla esperando", () => {
    expect(retryWhileWaking(0, new ApiRequestError("TOO_MANY_ATTEMPTS", 429))).toBe(false);
    expect(retryWhileWaking(0, new ApiRequestError("UNKNOWN_ERROR", 500))).toBe(false);
    expect(retryWhileWaking(0, new Error("otro"))).toBe(false);
  });

  it("deja de esperar al llegar al techo de reintentos", () => {
    const waking = new ApiRequestError("API_UNAVAILABLE", 503);

    expect(retryWhileWaking(WAKE_MAX_RETRIES - 1, waking)).toBe(true);
    expect(retryWhileWaking(WAKE_MAX_RETRIES, waking)).toBe(false);
  });

  it("la espera crece y se queda en 10 segundos, unos 75 en total", () => {
    const delays = Array.from({ length: WAKE_MAX_RETRIES }, (_, i) => wakeRetryDelay(i));

    expect(delays.slice(0, 5)).toEqual([1000, 2000, 4000, 8000, 10_000]);
    expect(delays.reduce((total, delay) => total + delay, 0)).toBe(75_000);
  });
});

describe("RequireSession mientras la API despierta", () => {
  it("sigue con el indicador y entra cuando la API responde, sin mostrar error", async () => {
    let calls = 0;
    mockApi({
      "GET /api/auth/me": () => {
        calls += 1;
        return calls === 1
          ? jsonResponse(503, { code: "API_UNAVAILABLE" })
          : jsonResponse(200, { username: "mechi", demo_expires_at: null });
      },
    });

    renderWithProviders(
      <Routes>
        <Route element={<RequireSession />}>
          <Route path="/" element={<p>Inicio</p>} />
        </Route>
      </Routes>,
    );

    expect(screen.getByRole("progressbar", { name: "Cargando" })).toBeInTheDocument();
    expect(await screen.findByText("Inicio", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.queryByText("Sin conexión con Rinde")).not.toBeInTheDocument();
    expect(calls).toBe(2);
  });
});
