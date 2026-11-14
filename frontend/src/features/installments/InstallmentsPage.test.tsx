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
import { aPlan } from "./fixtures";

const ACCOUNT = anAccount();
const BASE = {
  "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
  "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
  "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
  "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
  "POST /api/installments/due": jsonResponse(200, { created: 0 }),
};

describe("Compras en cuotas", () => {
  it("muestra cuánto falta, cuántas se registraron y la próxima cuota", async () => {
    mockApi({ ...BASE, "GET /api/installments": jsonResponse(200, [aPlan()]) });
    const { container } = renderWithProviders(<App />, { route: "/installments" });
    const user = userEvent.setup();

    const card = await screen.findByRole("listitem", { name: "Heladera" });
    expect(
      // La cuenta llega en otra consulta: se espera a que aparezca.
      await within(card).findByText(/^3 cuotas desde el 18 de septiembre.* · Galicia sueldo$/),
    ).toBeInTheDocument();
    expect(within(card).getByText("Falta pagar").nextSibling).toHaveTextContent("66.666,66");
    expect(within(card).getByText("1 de 3")).toBeInTheDocument();
    // El año se muestra solo si no es el actual: se compara el día y el mes.
    expect(within(card).getByText("Próxima cuota").nextSibling).toHaveTextContent(
      /18 de octubre.*33\.333,33/,
    );

    await user.click(within(card).getByText("Ver las cuotas"));
    const rows = within(card).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveAccessibleName(/^1 /);
    expect(rows[0]).toHaveTextContent("33.333,34");
    expect(rows[0]).toHaveTextContent("Registrada");
    expect(rows[2]).toHaveTextContent("Pendiente");
    await expectNoA11yViolations(container);
  });

  it("cancelar pide confirmación y dice qué queda", async () => {
    let cancelled = false;
    mockApi({
      ...BASE,
      "GET /api/installments": () =>
        jsonResponse(200, [
          aPlan(cancelled ? { cancelled_at: "2026-09-19T13:00:00Z", pending: "0.00" } : {}),
        ]),
      "POST /api/installments/7a8b9c0d-1e2f-4a3b-8c4d-5e6f7a8b9c0d/cancel": () => {
        cancelled = true;
        return jsonResponse(200, aPlan({ cancelled_at: "2026-09-19T13:00:00Z", pending: "0.00" }));
      },
    });
    renderWithProviders(<App />, { route: "/installments" });
    const user = userEvent.setup();

    const card = await screen.findByRole("listitem", { name: "Heladera" });
    await user.click(within(card).getByRole("button", { name: "Cancelar la compra" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Las cuotas que ya se registraron quedan como están");
    await user.click(within(dialog).getByRole("button", { name: "Cancelar la compra" }));

    expect(await within(card).findByText("Cancelada")).toBeInTheDocument();
    expect(
      within(card).queryByRole("button", { name: "Cancelar la compra" }),
    ).not.toBeInTheDocument();
  });

  it("sin compras, invita a registrar la primera", async () => {
    mockApi({ ...BASE, "GET /api/installments": jsonResponse(200, []) });
    renderWithProviders(<App />, { route: "/installments" });

    expect(
      await screen.findByRole("heading", { name: "No tenés compras en cuotas" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nueva compra en cuotas" })).toHaveAttribute(
      "href",
      "/installments/new",
    );
  });

  it("una cuota en la lista de movimientos dice cuál es", async () => {
    mockApi({
      ...BASE,
      "GET /api/transactions/balances": jsonResponse(200, []),
      "GET /api/history": jsonResponse(
        200,
        aHistoryPage([
          aTransaction({
            installment: { plan_id: aPlan().id, number: 2, count: 3 },
          }),
        ]),
      ),
    });
    renderWithProviders(<App />, { route: "/transactions" });

    expect(await screen.findByText(/Cuota 2 de 3/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cuotas" })).toHaveAttribute("href", "/installments");
  });

  it("al abrir la app genera las cuotas vencidas y, si hubo, recarga los saldos", async () => {
    const fetchMock = mockApi({
      ...BASE,
      "POST /api/installments/due": jsonResponse(200, { created: 2 }),
      "GET /api/installments": jsonResponse(200, []),
    });
    renderWithProviders(<App />, { route: "/installments" });

    await screen.findByRole("heading", { name: "No tenés compras en cuotas" });
    await vi.waitFor(() => {
      const listings = fetchMock.mock.calls.filter(
        ([input, init]) => input === "/api/installments" && (init?.method ?? "GET") === "GET",
      );
      // Una vez al cargar y otra después de generar.
      expect(listings.length).toBeGreaterThanOrEqual(2);
    });
    const due = fetchMock.mock.calls.filter(([input]) => input === "/api/installments/due");
    expect(due).toHaveLength(1);
  });
});
