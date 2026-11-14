import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import { EXPENSE_CATEGORY, INCOME_CATEGORY } from "../transactions/fixtures";
import { aPlan } from "./fixtures";

const ACCOUNT = anAccount();
const BASE = {
  "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
  "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
  "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
  "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
  "GET /api/installments": jsonResponse(200, [aPlan()]),
  "POST /api/installments/due": jsonResponse(200, { created: 0 }),
};

async function choose(user: ReturnType<typeof userEvent.setup>, field: RegExp, option: string) {
  await user.click(screen.getByRole("button", { name: field }));
  await user.click(await screen.findByRole("option", { name: option }));
}

describe("Nueva compra en cuotas", () => {
  it("manda el total como texto, la cantidad y una clave de idempotencia", async () => {
    let sent: unknown = null;
    let key: string | null = null;
    mockApi({
      ...BASE,
      "POST /api/installments": (init) => {
        sent = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        key = new Headers(init?.headers).get("Idempotency-Key");
        return jsonResponse(201, aPlan());
      },
    });
    const { container } = renderWithProviders(<App />, { route: "/installments/new" });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Total a pagar"), "100.000,00");
    await choose(user, /Cantidad de cuotas/, "3 cuotas");
    await choose(user, /Categoría/, "Supermercado");
    await user.type(screen.getByLabelText("Descripción (opcional)"), "Heladera");
    await expectNoA11yViolations(container);
    await user.click(screen.getByRole("button", { name: "Registrar la compra" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Compras en cuotas" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Registraste la compra en cuotas.").length).toBeGreaterThan(0);
    // La coma que se escribe en Argentina viaja como punto decimal; el reparto lo hace el servidor.
    expect(sent).toMatchObject({
      account_id: ACCOUNT.id,
      category_id: EXPENSE_CATEGORY.id,
      total: "100000.00",
      count: 3,
      description: "Heladera",
    });
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("pide el total, la cantidad y la categoría antes de enviar", async () => {
    mockApi(BASE);
    renderWithProviders(<App />, { route: "/installments/new" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Registrar la compra" }));
    expect(screen.getByText("Escribí el total.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Total a pagar"), "1000");
    await user.click(screen.getByRole("button", { name: "Registrar la compra" }));
    expect(screen.getByText("Elegí entre 2 y 48 cuotas.")).toBeInTheDocument();

    await choose(user, /Cantidad de cuotas/, "2 cuotas");
    await user.click(screen.getByRole("button", { name: "Registrar la compra" }));
    expect(screen.getByText("Elegí una categoría.")).toBeInTheDocument();
  });

  it("muestra el error del servidor junto al campo que lo causa", async () => {
    mockApi({
      ...BASE,
      "POST /api/installments": jsonResponse(422, { code: "INSTALLMENT_AMOUNT_TOO_SMALL" }),
    });
    renderWithProviders(<App />, { route: "/installments/new" });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Total a pagar"), "0,02");
    await choose(user, /Cantidad de cuotas/, "3 cuotas");
    await choose(user, /Categoría/, "Supermercado");
    await user.click(screen.getByRole("button", { name: "Registrar la compra" }));

    expect(
      await screen.findByText(/no alcanza para que cada cuota sea de al menos un centavo/),
    ).toBeInTheDocument();
  });
});
