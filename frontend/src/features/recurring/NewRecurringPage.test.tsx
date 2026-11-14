import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import { EXPENSE_CATEGORY, INCOME_CATEGORY } from "../transactions/fixtures";
import { aRule } from "./fixtures";

const ACCOUNT = anAccount();
const BASE = {
  "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
  "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
  "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
  "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
  "GET /api/recurring": jsonResponse(200, [aRule()]),
  "POST /api/installments/due": jsonResponse(200, { created: 0 }),
  "POST /api/recurring/due": jsonResponse(200, { created: 0 }),
};

async function choose(user: ReturnType<typeof userEvent.setup>, field: RegExp, option: string) {
  await user.click(screen.getByRole("button", { name: field }));
  await user.click(await screen.findByRole("option", { name: option }));
}

describe("Nuevo movimiento recurrente", () => {
  it("manda el monto como texto, la frecuencia y una clave de idempotencia", async () => {
    let sent: unknown = null;
    let key: string | null = null;
    mockApi({
      ...BASE,
      "POST /api/recurring": (init) => {
        sent = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        key = new Headers(init?.headers).get("Idempotency-Key");
        return jsonResponse(201, aRule());
      },
    });
    const { container } = renderWithProviders(<App />, { route: "/recurring/new" });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Monto"), "450.000,00");
    await choose(user, /Categoría/, "Supermercado");
    await choose(user, /Cada cuánto/, "Todas las semanas");
    await expectNoA11yViolations(container);
    await user.click(screen.getByRole("button", { name: "Registrar" }));

    await screen.findByRole("heading", { name: "Movimientos recurrentes" });
    expect(screen.getAllByText("Registraste el movimiento recurrente.").length).toBeGreaterThan(0);
    expect(sent).toMatchObject({
      account_id: ACCOUNT.id,
      kind: "expense",
      amount: "450000.00",
      category_id: EXPENSE_CATEGORY.id,
      frequency: "weekly",
      description: null,
    });
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("un ingreso ofrece solo categorías de ingresos", async () => {
    mockApi(BASE);
    renderWithProviders(<App />, { route: "/recurring/new" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("radio", { name: "Ingreso" }));
    await user.click(screen.getByRole("button", { name: /Categoría/ }));

    expect(await screen.findByRole("option", { name: "Sueldo" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Supermercado" })).not.toBeInTheDocument();
  });

  it("pide el monto y la categoría antes de enviar", async () => {
    const fetchMock = mockApi(BASE);
    renderWithProviders(<App />, { route: "/recurring/new" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Registrar" }));

    expect(await screen.findByText("Escribí el monto.")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) => input === "/api/recurring" && init?.method === "POST",
      ),
    ).toBe(false);
  });

  it("una primera vez fuera de rango se marca en la fecha", async () => {
    mockApi({
      ...BASE,
      "POST /api/recurring": jsonResponse(422, { code: "RECURRING_START_OUT_OF_RANGE" }),
    });
    renderWithProviders(<App />, { route: "/recurring/new" });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Monto"), "1000");
    await choose(user, /Categoría/, "Supermercado");
    await user.click(screen.getByRole("button", { name: "Registrar" }));

    // Junto a la fecha, no arriba del formulario.
    const date = screen.getByLabelText("Primera vez");
    await waitFor(() => {
      expect(date).toHaveAccessibleDescription(
        "La primera vez tiene que ser hasta un año antes o un año después de hoy.",
      );
    });
    expect(date).toBeInvalid();
  });
});
