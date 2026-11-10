import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { aQuote } from "../rates/fixtures";
import { aBalance } from "../transactions/fixtures";
import { anAccount } from "./fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };
const PESOS_AT_MEP = { reference_currency: "ARS", rate_type: "mep" };

const GALICIA = anAccount();
const DOLLARS = anAccount({
  id: "5c4b3a29-1807-4f6e-9d5c-4b3a29180706",
  name: "Caja en dólares",
  currency: "USD",
});
const LEMON = anAccount({
  id: "7f1e2d3c-4b5a-4968-8776-655443322110",
  name: "Lemon",
  kind: "crypto_wallet",
  currency: "BTC",
});
const BALANCES = [
  aBalance(),
  aBalance({ account_id: DOLLARS.id, amount: "1500.00", currency: "USD" }),
  aBalance({ account_id: LEMON.id, amount: "0.01000000", currency: "BTC" }),
];
const CONVERSION_URL = "GET /api/rates/mep/conversion?amount=1500.00&currency=USD&target=ARS";

function conversion() {
  return jsonResponse(200, {
    original: { amount: "1500.00", currency: "USD" },
    converted: { amount: "2340300.00", currency: "ARS" },
    rate: "1560.20000000",
    quote: aQuote(),
  });
}

describe("Equivalente de cada cuenta", () => {
  it("muestra las cuentas en dólares convertidas a pesos, con el dólar elegido", async () => {
    const fetchMock = mockApi({
      ...SESSION,
      "GET /api/accounts": jsonResponse(200, [GALICIA, DOLLARS, LEMON]),
      "GET /api/transactions/balances": jsonResponse(200, BALANCES),
      "GET /api/preferences": jsonResponse(200, PESOS_AT_MEP),
      [CONVERSION_URL]: conversion(),
    });
    renderWithProviders(<App />, { route: "/accounts" });

    const dollars = await screen.findByRole("link", { name: /Caja en dólares/ });
    expect(await within(dollars).findByText(/≈\s\$\s2\.340\.300,00 al MEP/)).toBeInTheDocument();
    // El monto viaja como string decimal, tal como vino del servidor.
    const asked = fetchMock.mock.calls
      .map(([input]) => (typeof input === "string" ? input : ""))
      .filter((url) => url.startsWith("/api/rates/mep/conversion"));
    expect(asked).toEqual(["/api/rates/mep/conversion?amount=1500.00&currency=USD&target=ARS"]);
    // En pesos no hay nada que convertir, y Bitcoin todavía no tiene cotización.
    expect(within(screen.getByRole("link", { name: /Galicia/ })).queryByText(/≈/)).toBeNull();
    expect(within(screen.getByRole("link", { name: /Lemon/ })).queryByText(/≈/)).toBeNull();
  });

  it("dice que no hay cotización en vez de inventar un número", async () => {
    mockApi({
      ...SESSION,
      "GET /api/accounts": jsonResponse(200, [DOLLARS]),
      "GET /api/transactions/balances": jsonResponse(200, BALANCES),
      "GET /api/preferences": jsonResponse(200, PESOS_AT_MEP),
      [CONVERSION_URL]: jsonResponse(503, { code: "RATES_UNAVAILABLE" }),
    });
    renderWithProviders(<App />, { route: "/accounts" });

    const dollars = await screen.findByRole("link", { name: /Caja en dólares/ });
    expect(await within(dollars).findByText("Sin cotización para convertir")).toBeInTheDocument();
  });

  it("sin preferencias cargadas no muestra ningún equivalente", async () => {
    const fetchMock = mockApi({
      ...SESSION,
      "GET /api/accounts": jsonResponse(200, [DOLLARS]),
      "GET /api/transactions/balances": jsonResponse(200, BALANCES),
      "GET /api/preferences": jsonResponse(500, {}),
    });
    renderWithProviders(<App />, { route: "/accounts" });

    await screen.findByRole("link", { name: /Caja en dólares/ });
    const asked = fetchMock.mock.calls.map(([input]) => (typeof input === "string" ? input : ""));
    expect(asked.some((url) => url.includes("/conversion"))).toBe(false);
  });
});
