import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse, renderWithProviders } from "../../test/render";
import { HealthStatus } from "./HealthStatus";

describe("HealthStatus", () => {
  it("muestra que se está consultando mientras espera la respuesta", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderWithProviders(<HealthStatus />);

    expect(screen.getByRole("status")).toHaveTextContent("Consultando el estado…");
  });

  it("informa que todo está operativo", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { status: "ok", database: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<HealthStatus />);

    expect(
      await screen.findByText("La API y la base de datos están operativas."),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/health/ready", expect.any(Object));
  });

  it("avisa cuando la base de datos no está disponible", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(jsonResponse(503, { status: "unavailable", database: "unavailable" })),
    );

    renderWithProviders(<HealthStatus />);

    expect(
      await screen.findByText("La API responde, pero la base de datos no está disponible."),
    ).toBeInTheDocument();
  });

  it("avisa cuando la API no responde", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    renderWithProviders(<HealthStatus />);

    expect(await screen.findByText("No se pudo contactar a la API.")).toBeInTheDocument();
  });

  it("trata un estado inesperado como error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(500, {})));

    renderWithProviders(<HealthStatus />);

    expect(await screen.findByText("No se pudo contactar a la API.")).toBeInTheDocument();
  });
});
