import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import {
  aHistoryPage,
  aTransaction,
  EXPENSE_CATEGORY,
  INCOME_CATEGORY,
} from "../transactions/fixtures";
import { aRule } from "./fixtures";

const ACCOUNT = anAccount();
const RULE = aRule();
const BASE = {
  "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
  "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
  "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
  "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
  "POST /api/installments/due": jsonResponse(200, { created: 0 }),
  "POST /api/recurring/due": jsonResponse(200, { created: 0 }),
};

describe("Movimientos recurrentes", () => {
  it("muestra el monto con su signo, cada cuánto, lo registrado y la próxima vez", async () => {
    mockApi({ ...BASE, "GET /api/recurring": jsonResponse(200, [RULE]) });
    const { container } = renderWithProviders(<App />, { route: "/recurring" });

    const card = await screen.findByRole("listitem", { name: "Alquiler" });
    expect(
      // La cuenta llega en otra consulta: se espera a que aparezca.
      await within(card).findByText(/^Todos los meses · desde el 10 de agosto.* · Galicia sueldo$/),
    ).toBeInTheDocument();
    expect(within(card).getByText("Monto").nextSibling).toHaveTextContent(/−.*450\.000,00/);
    expect(within(card).getByText("2 veces")).toBeInTheDocument();
    // El año se muestra solo si no es el actual: se compara el día y el mes.
    expect(within(card).getByText("Próxima vez").nextSibling).toHaveTextContent(/10 de octubre/);
    expect(
      within(card).getByRole("link", { name: "Cambiar el monto de Alquiler" }),
    ).toHaveAttribute("href", `/recurring/${RULE.id}`);
    await expectNoA11yViolations(container);
  });

  it("cancelar pide confirmación, dice qué queda y deja de ofrecer cambios", async () => {
    let cancelled = false;
    const done = { cancelled_at: "2026-09-19T13:00:00Z", next_on: null };
    mockApi({
      ...BASE,
      "GET /api/recurring": () => jsonResponse(200, [aRule(cancelled ? done : {})]),
      [`POST /api/recurring/${RULE.id}/cancel`]: () => {
        cancelled = true;
        return jsonResponse(200, aRule(done));
      },
    });
    renderWithProviders(<App />, { route: "/recurring" });
    const user = userEvent.setup();

    const card = await screen.findByRole("listitem", { name: "Alquiler" });
    await user.click(within(card).getByRole("button", { name: "Cancelar" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Lo que ya se registró queda como está");
    await user.click(within(dialog).getByRole("button", { name: "Cancelar el recurrente" }));

    expect(await within(card).findByText("Cancelado")).toBeInTheDocument();
    expect(within(card).queryByText("Próxima vez")).not.toBeInTheDocument();
    expect(within(card).queryByRole("link", { name: /Cambiar el monto/ })).not.toBeInTheDocument();
  });

  it("sin reglas, invita a registrar la primera", async () => {
    mockApi({ ...BASE, "GET /api/recurring": jsonResponse(200, []) });
    renderWithProviders(<App />, { route: "/recurring" });

    expect(
      await screen.findByRole("heading", { name: "No tenés movimientos recurrentes" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nuevo recurrente" })).toHaveAttribute(
      "href",
      "/recurring/new",
    );
  });

  it("un movimiento generado dice que es recurrente en la lista", async () => {
    mockApi({
      ...BASE,
      "GET /api/transactions/balances": jsonResponse(200, []),
      "GET /api/history": jsonResponse(
        200,
        aHistoryPage([aTransaction({ recurrence: { rule_id: RULE.id, number: 2 } })]),
      ),
    });
    renderWithProviders(<App />, { route: "/transactions" });

    expect(await screen.findByText(/ · Recurrente$/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Recurrentes" })).toHaveAttribute("href", "/recurring");
  });

  it("al abrir la app genera lo vencido y, si hubo, recarga los saldos", async () => {
    const fetchMock = mockApi({
      ...BASE,
      "POST /api/recurring/due": jsonResponse(200, { created: 1 }),
      "GET /api/recurring": jsonResponse(200, []),
    });
    renderWithProviders(<App />, { route: "/recurring" });

    await screen.findByRole("heading", { name: "No tenés movimientos recurrentes" });
    await vi.waitFor(() => {
      const listings = fetchMock.mock.calls.filter(
        ([input, init]) => input === "/api/recurring" && (init?.method ?? "GET") === "GET",
      );
      // Una vez al cargar y otra después de generar.
      expect(listings.length).toBeGreaterThanOrEqual(2);
    });
    const due = fetchMock.mock.calls.filter(([input]) => input === "/api/recurring/due");
    expect(due).toHaveLength(1);
  });
});
