import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import { aPage, aTransaction, EXPENSE_CATEGORY, INCOME_CATEGORY } from "./fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };
const ACCOUNT = anAccount();

const BASE = {
  ...SESSION,
  "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
  "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
  "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
  "GET /api/transactions/balances": jsonResponse(200, []),
  "GET /api/transactions": jsonResponse(200, aPage([])),
};

async function fillAmount(value: string) {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Monto"), value);
  return user;
}

describe("Registrar un movimiento", () => {
  it("manda el monto como texto y una clave de idempotencia", async () => {
    let sent: unknown = null;
    let key: string | null = null;
    mockApi({
      ...BASE,
      "POST /api/transactions": (init) => {
        sent = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        key = new Headers(init?.headers).get("Idempotency-Key");
        return jsonResponse(201, aTransaction());
      },
    });
    renderWithProviders(<App />, { route: "/transactions/new" });

    const user = await fillAmount("15300,50");
    await user.click(screen.getByRole("button", { name: /Categoría/ }));
    await user.click(await screen.findByRole("option", { name: "Supermercado" }));
    await user.click(screen.getByRole("button", { name: "Registrar" }));

    await screen.findByRole("heading", { name: "Movimientos" });
    // La coma que se escribe en Argentina viaja como punto decimal.
    expect(sent).toMatchObject({
      account_id: ACCOUNT.id,
      kind: "expense",
      amount: "15300.50",
      category_id: EXPENSE_CATEGORY.id,
    });
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("pide monto y categoría antes de enviar", async () => {
    const fetchMock = mockApi(BASE);
    renderWithProviders(<App />, { route: "/transactions/new" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Registrar" }));
    expect(screen.getByLabelText("Monto")).toHaveAccessibleDescription("Escribí un monto.");

    await user.type(screen.getByLabelText("Monto"), "1500");
    await user.click(screen.getByRole("button", { name: "Registrar" }));

    expect(screen.getByRole("button", { name: /Categoría/ })).toHaveAccessibleDescription(
      "Elegí una categoría.",
    );
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("al cambiar de tipo ofrece las categorías de ese tipo", async () => {
    mockApi(BASE);
    renderWithProviders(<App />, { route: "/transactions/new" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("radio", { name: "Ingreso" }));
    await user.click(screen.getByRole("button", { name: /Categoría/ }));

    expect(await screen.findByRole("option", { name: "Sueldo" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Supermercado" })).not.toBeInTheDocument();
  });

  it("muestra junto al campo lo que rechaza el servidor", async () => {
    mockApi({
      ...BASE,
      "POST /api/transactions": jsonResponse(422, { code: "TRANSACTION_DATE_IN_FUTURE" }),
    });
    renderWithProviders(<App />, { route: "/transactions/new" });

    const user = await fillAmount("1500");
    await user.click(screen.getByRole("button", { name: /Categoría/ }));
    await user.click(await screen.findByRole("option", { name: "Supermercado" }));
    await user.click(screen.getByRole("button", { name: "Registrar" }));

    expect(await screen.findByText("La fecha no puede ser futura.")).toBeInTheDocument();
  });

  it("sin cuentas, primero manda a abrir una", async () => {
    mockApi({ ...BASE, "GET /api/accounts": jsonResponse(200, []) });
    renderWithProviders(<App />, { route: "/transactions/new" });

    expect(
      await screen.findByRole("heading", { name: "Primero abrí una cuenta" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir una cuenta" })).toHaveAttribute(
      "href",
      "/accounts/new",
    );
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi(BASE);
    const { container } = renderWithProviders(<App />, { route: "/transactions/new" });

    await screen.findByLabelText("Monto");

    await expectNoA11yViolations(container);
  });
});
