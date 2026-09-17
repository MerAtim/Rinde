import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "./fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };

const GALICIA = anAccount();
const LEMON = anAccount({
  id: "7f1e2d3c-4b5a-4968-8776-655443322110",
  name: "Lemon",
  kind: "crypto_wallet",
  currency: "BTC",
});
const OLD_CASH = anAccount({
  id: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  name: "Efectivo viejo",
  kind: "cash",
  archived_at: "2026-09-18T10:00:00Z",
});

describe("Cuentas", () => {
  it("lista las cuentas activas con su tipo y su moneda", async () => {
    mockApi({ ...SESSION, "GET /api/accounts": jsonResponse(200, [GALICIA, LEMON]) });
    renderWithProviders(<App />, { route: "/accounts" });

    const galicia = await screen.findByRole("link", { name: /Galicia sueldo/ });
    expect(galicia).toHaveAttribute("href", `/accounts/${GALICIA.id}`);
    expect(galicia).toHaveTextContent("Banco");
    expect(galicia).toHaveAccessibleName(/Pesos argentinos \(ARS\)/);
    expect(screen.getByRole("link", { name: /Lemon/ })).toHaveTextContent("Billetera cripto");
  });

  it("muestra las archivadas cuando se pide", async () => {
    mockApi({
      ...SESSION,
      "GET /api/accounts": jsonResponse(200, [GALICIA]),
      "GET /api/accounts?include_archived=true": jsonResponse(200, [GALICIA, OLD_CASH]),
    });
    renderWithProviders(<App />, { route: "/accounts" });
    const user = userEvent.setup();

    await screen.findByRole("link", { name: /Galicia sueldo/ });
    expect(screen.queryByRole("link", { name: /Efectivo viejo/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Mostrar las archivadas" }));

    const archived = await screen.findByRole("link", { name: /Efectivo viejo/ });
    expect(within(archived).getByText("Archivada")).toBeInTheDocument();
  });

  it("abre directo con las archivadas si la dirección lo indica", async () => {
    mockApi({
      ...SESSION,
      "GET /api/accounts?include_archived=true": jsonResponse(200, [OLD_CASH]),
    });
    renderWithProviders(<App />, { route: "/accounts?archived=1" });

    expect(await screen.findByRole("link", { name: /Efectivo viejo/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Mostrar las archivadas" })).toBeChecked();
  });

  it("sin cuentas, explica qué son y ofrece abrir la primera", async () => {
    mockApi({ ...SESSION, "GET /api/accounts": jsonResponse(200, []) });
    renderWithProviders(<App />, { route: "/accounts" });

    expect(
      await screen.findByRole("heading", { name: "Todavía no tenés cuentas" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir tu primera cuenta" })).toHaveAttribute(
      "href",
      "/accounts/new",
    );
    // Una sola acción principal por pantalla: la del encabezado se oculta.
    expect(screen.queryByRole("link", { name: "Abrir cuenta" })).not.toBeInTheDocument();
  });

  it("si falla la carga, lo dice y permite reintentar", async () => {
    let attempts = 0;
    mockApi({
      ...SESSION,
      "GET /api/accounts": () => {
        attempts += 1;
        return attempts === 1 ? jsonResponse(500) : jsonResponse(200, [GALICIA]);
      },
    });
    renderWithProviders(<App />, { route: "/accounts" });
    const user = userEvent.setup();

    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar tus cuentas.");
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByRole("link", { name: /Galicia sueldo/ })).toBeInTheDocument();
  });

  it("si la sesión venció, lleva a ingresar", async () => {
    mockApi({
      ...SESSION,
      "GET /api/accounts": jsonResponse(401, { code: "NOT_AUTHENTICATED" }),
    });
    renderWithProviders(<App />, { route: "/accounts" });

    expect(await screen.findByRole("heading", { name: "Ingresá a Rinde" })).toBeInTheDocument();
  });

  it("marca Cuentas en la navegación principal", async () => {
    mockApi({ ...SESSION, "GET /api/accounts": jsonResponse(200, [GALICIA]) });
    renderWithProviders(<App />, { route: "/accounts" });

    const nav = await screen.findByRole("navigation", { name: "Navegación principal" });
    expect(within(nav).getByRole("link", { name: "Cuentas" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi({ ...SESSION, "GET /api/accounts": jsonResponse(200, [GALICIA, OLD_CASH]) });
    const { container } = renderWithProviders(<App />, { route: "/accounts" });

    await screen.findByRole("link", { name: /Galicia sueldo/ });

    await expectNoA11yViolations(container);
  });
});
