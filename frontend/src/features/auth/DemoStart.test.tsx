import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

const DEMO = { username: "demo-k3v9q2m7xa", demo_expires_at: "2026-11-15T20:30:00Z" };
const SIGNED_OUT = jsonResponse(401, { code: "NOT_AUTHENTICATED" });

describe("Probar la demo", () => {
  it("abre una demo propia y avisa en todas las pantallas a qué hora se borra", async () => {
    let sent: RequestInit | undefined;
    const fetchMock = mockApi({
      "GET /api/auth/me": SIGNED_OUT,
      "POST /api/auth/demo": (init) => {
        sent = init;
        return jsonResponse(201, DEMO);
      },
    });
    const { container } = renderWithProviders(<App />, { route: "/login" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Probar la demo" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Resumen" })).toBeInTheDocument();
    const banner = screen.getByRole("region", { name: "Cuenta demo" });
    expect(banner).toHaveTextContent(
      /^Estás en una demo con datos de ejemplo\. Se borra a las \d{1,2}:\d{2}.* con todo lo que cargues\./,
    );
    // La respuesta ya trae la sesión: no hace falta volver a pedir /me.
    const sessionChecks = fetchMock.mock.calls.filter(([input]) => input === "/api/auth/me");
    expect(sessionChecks).toHaveLength(1);
    expect(new Headers(sent?.headers).get("X-Requested-With")).toBe("rinde");
    await expectNoA11yViolations(container);
  });

  it("con el límite por origen, dice que ya abrió varias y ofrece crear una cuenta", async () => {
    mockApi({
      "GET /api/auth/me": SIGNED_OUT,
      "POST /api/auth/demo": jsonResponse(429, { code: "TOO_MANY_ATTEMPTS" }),
    });
    renderWithProviders(<App />, { route: "/login" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Probar la demo" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya abriste varias demos en la última hora. Probá más tarde o creá una cuenta.",
    );
  });

  it("con el servicio lleno, pide volver en un rato", async () => {
    mockApi({
      "GET /api/auth/me": SIGNED_OUT,
      "POST /api/auth/demo": jsonResponse(503, { code: "DEMO_UNAVAILABLE" }),
    });
    renderWithProviders(<App />, { route: "/login" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Probar la demo" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Hay muchas demos abiertas en este momento. Probá de nuevo en un rato.",
    );
  });

  it("desde la demo se puede ir al registro, y la cuenta nueva la reemplaza", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(200, DEMO) });
    renderWithProviders(<App />, { route: "/" });
    const user = userEvent.setup();

    const banner = await screen.findByRole("region", { name: "Cuenta demo" });
    await user.click(within(banner).getByRole("link", { name: "Crear mi cuenta" }));

    // Una demo no es la cuenta de nadie: el registro no la manda de vuelta al inicio.
    expect(await screen.findByRole("heading", { name: "Creá tu cuenta" })).toBeInTheDocument();
  });

  it("una cuenta común no ve el aviso", async () => {
    mockApi({
      "GET /api/auth/me": jsonResponse(200, { username: "mechi", demo_expires_at: null }),
    });
    renderWithProviders(<App />, { route: "/" });

    await screen.findByRole("heading", { level: 1, name: "Resumen" });

    expect(screen.queryByRole("region", { name: "Cuenta demo" })).not.toBeInTheDocument();
  });
});
