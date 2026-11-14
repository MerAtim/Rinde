import { screen } from "@testing-library/react";
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
const RULE = aRule();
const BASE = {
  "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
  "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
  "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
  "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
  "GET /api/recurring": jsonResponse(200, [RULE]),
  "POST /api/installments/due": jsonResponse(200, { created: 0 }),
  "POST /api/recurring/due": jsonResponse(200, { created: 0 }),
};

describe("Cambiar el monto de un movimiento recurrente", () => {
  it("manda el monto nuevo y vuelve a la lista avisando desde cuándo vale", async () => {
    let sent: unknown = null;
    mockApi({
      ...BASE,
      [`PATCH /api/recurring/${RULE.id}`]: (init) => {
        sent = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        return jsonResponse(200, aRule({ amount: "520000.00" }));
      },
    });
    const { container } = renderWithProviders(<App />, { route: `/recurring/${RULE.id}` });
    const user = userEvent.setup();

    const amount = await screen.findByLabelText("Monto nuevo");
    expect(amount).toHaveValue("450000.00");
    await user.clear(amount);
    await user.type(amount, "520.000,00");
    await expectNoA11yViolations(container);
    await user.click(screen.getByRole("button", { name: "Guardar el monto" }));

    await screen.findByRole("heading", { name: "Movimientos recurrentes" });
    expect(screen.getAllByText(/Vale desde la próxima vez/).length).toBeGreaterThan(0);
    expect(sent).toEqual({ amount: "520000.00", description: "Alquiler" });
  });

  it("una regla cancelada o ajena se informa como inexistente", async () => {
    mockApi({
      ...BASE,
      "GET /api/recurring": jsonResponse(200, [aRule({ cancelled_at: "2026-09-19T13:00:00Z" })]),
    });
    renderWithProviders(<App />, { route: `/recurring/${RULE.id}` });

    expect(
      await screen.findByText("Ese movimiento recurrente no existe o ya se canceló."),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Monto nuevo")).not.toBeInTheDocument();
  });
});
