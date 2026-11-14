import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import { aTransaction, EXPENSE_CATEGORY, INCOME_CATEGORY } from "./fixtures";

const TRANSACTION = aTransaction();
const INSTALLMENT = aTransaction({
  installment: { plan_id: "7c0e1d2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f", number: 2, count: 6 },
});

function renderEdit(transaction: typeof TRANSACTION) {
  const account = anAccount({ id: transaction.account_id });
  mockApi({
    "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
    "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
    "GET /api/accounts?include_archived=true": jsonResponse(200, [account]),
    [`GET /api/transactions/${transaction.id}`]: jsonResponse(200, transaction),
  });
  return renderWithProviders(<App />, { route: `/transactions/${transaction.id}` });
}

describe("Editar un movimiento", () => {
  it("deja cambiar el tipo de un movimiento común", async () => {
    renderEdit(TRANSACTION);

    expect(await screen.findByRole("radio", { name: "Ingreso" })).toBeEnabled();
    expect(screen.queryByText("Una cuota es siempre un gasto.")).not.toBeInTheDocument();
  });

  it("no deja pasar una cuota a ingreso, y dice por qué", async () => {
    const { container } = renderEdit(INSTALLMENT);

    expect(await screen.findByRole("radio", { name: "Ingreso" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Gasto" })).toBeChecked();
    expect(screen.getByText("Una cuota es siempre un gasto.")).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });
});
