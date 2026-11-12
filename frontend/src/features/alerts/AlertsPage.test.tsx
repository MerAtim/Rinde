import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { AlertsPage } from "./AlertsPage";
import { aFeed } from "./fixtures";

// El mes en curso sale del reloj: noviembre de 2026, a las 12 de Buenos Aires.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-10T15:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

function rowOf(text: RegExp): HTMLElement {
  const row = screen.getByText(text).closest("li");
  if (!row) {
    throw new Error(`no hay fila para ${String(text)}`);
  }
  return row;
}

describe("AlertsPage", () => {
  it("muestra cada alerta con su estado en texto, lo gastado y un enlace a su mes", async () => {
    mockApi({ "GET /api/alerts": jsonResponse(200, aFeed()) });
    const { container } = renderWithProviders(<AlertsPage />, { route: "/alerts" });

    expect(await screen.findByText(/Alquiler llegó al tope/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Alertas" })).toBeInTheDocument();

    const rent = rowOf(/Alquiler llegó al tope/);
    expect(within(rent).getByText("Llegaste al tope")).toBeInTheDocument();
    // Sin leer se dice con texto, además del fondo.
    expect(within(rent).getByText("Nueva")).toBeInTheDocument();
    expect(rent).toHaveTextContent(/Llevabas US\$\s512,50 de US\$\s500,00 en noviembre de 2026/);
    // La hora es la de Argentina: las 15 UTC son las 12.
    expect(rent).toHaveTextContent(/10 nov 2026, 12:00/);
    expect(
      within(rent).getByRole("link", { name: "Ver los presupuestos de noviembre de 2026" }),
    ).toHaveAttribute("href", "/budgets");

    const food = rowOf(/Supermercado llegó al 80 % del presupuesto/);
    expect(within(food).getByText("Cerca del tope")).toBeInTheDocument();
    expect(within(food).queryByText("Nueva")).not.toBeInTheDocument();
    // Un mes que ya pasó va en la URL de presupuestos (ADR-0020).
    expect(
      within(food).getByRole("link", { name: "Ver los presupuestos de octubre de 2026" }),
    ).toHaveAttribute("href", "/budgets?month=2026-10");

    await expectNoA11yViolations(container);
  });

  it("marca como leídas solo las que se ven sin leer, y lleva el foco al título", async () => {
    let feed = aFeed();
    const fetchMock = mockApi({
      "GET /api/alerts": () => jsonResponse(200, feed),
      "POST /api/alerts/read": () => {
        feed = aFeed({
          unread: 0,
          alerts: aFeed().alerts.map((alert) => ({ ...alert, read: true })),
        });
        return new Response(null, { status: 204 });
      },
    });
    renderWithProviders(<AlertsPage />, { route: "/alerts" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Marcar como leídas" }));

    const body = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.body;
    expect(typeof body === "string" ? JSON.parse(body) : body).toEqual({
      ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    });
    expect(await screen.findByRole("heading", { level: 1, name: "Alertas" })).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Marcar como leídas" })).not.toBeInTheDocument();
    expect(screen.queryByText("Nueva")).not.toBeInTheDocument();
  });

  it("si no pudo marcarlas, lo dice y deja el botón", async () => {
    mockApi({
      "GET /api/alerts": jsonResponse(200, aFeed()),
      "POST /api/alerts/read": jsonResponse(500, {}),
    });
    renderWithProviders(<AlertsPage />, { route: "/alerts" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Marcar como leídas" }));

    expect(
      await screen.findByText("No pudimos marcarlas como leídas. Probá de nuevo."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Marcar como leídas" })).toBeEnabled();
  });

  it("sin alertas explica cuándo van a aparecer", async () => {
    mockApi({ "GET /api/alerts": jsonResponse(200, { unread: 0, alerts: [] }) });
    renderWithProviders(<AlertsPage />, { route: "/alerts" });

    expect(await screen.findByText("No tenés alertas")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Marcar como leídas" })).not.toBeInTheDocument();
  });

  it("si no cargan, ofrece reintentar", async () => {
    let fails = true;
    mockApi({
      "GET /api/alerts": () => (fails ? jsonResponse(500, {}) : jsonResponse(200, aFeed())),
    });
    renderWithProviders(<AlertsPage />, { route: "/alerts" });
    const user = userEvent.setup();

    expect(await screen.findByText("No pudimos cargar tus alertas.")).toBeInTheDocument();
    fails = false;
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText(/Alquiler llegó al tope/)).toBeInTheDocument();
  });
});
