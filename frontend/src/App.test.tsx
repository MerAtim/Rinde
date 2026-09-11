import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { expectNoA11yViolations } from "./test/a11y";
import { mockApi } from "./test/api";
import { jsonResponse, renderWithProviders } from "./test/render";

describe("App", () => {
  it("sin sesión lleva a la pantalla de ingreso", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }) });

    renderWithProviders(<App />, { route: "/" });

    expect(await screen.findByRole("heading", { name: "Ingresá a Rinde" })).toBeInTheDocument();
  });

  it("con sesión muestra el inicio, y al cerrarla vuelve al ingreso", async () => {
    mockApi({
      "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
      "POST /api/auth/logout": new Response(null, { status: 204 }),
    });
    renderWithProviders(<App />, { route: "/" });
    const user = userEvent.setup();

    expect(await screen.findByText("Hola, mechi")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "¿Me rinde el sueldo?" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(await screen.findByRole("heading", { name: "Ingresá a Rinde" })).toBeInTheDocument();
  });

  it("con sesión abierta, las pantallas de ingreso llevan al inicio", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) });

    renderWithProviders(<App />, { route: "/signup" });

    expect(await screen.findByText("Hola, mechi")).toBeInTheDocument();
  });

  it("la pantalla del código sin código lleva al inicio", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }) });

    renderWithProviders(<App />, { route: "/recovery-code" });

    expect(await screen.findByRole("heading", { name: "Ingresá a Rinde" })).toBeInTheDocument();
  });

  it("el inicio no tiene problemas de accesibilidad", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) });
    const { container } = renderWithProviders(<App />, { route: "/" });

    await screen.findByText("Hola, mechi");

    await expectNoA11yViolations(container);
  });
});
