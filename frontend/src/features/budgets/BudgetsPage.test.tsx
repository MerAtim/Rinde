import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { EXPENSE_CATEGORY } from "../transactions/fixtures";
import { BudgetsPage } from "./BudgetsPage";
import { aBudget, aBudgetMonth } from "./fixtures";

// El mes en curso sale del reloj: se fija en noviembre de 2026, a las 12 de Buenos Aires.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-11-10T15:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

function rowOf(name: string): HTMLElement {
  const row = screen.getByText(name).closest("li");
  if (!row) {
    throw new Error(`no hay fila para ${name}`);
  }
  return row;
}

describe("BudgetsPage", () => {
  it("muestra cada tope con lo gastado, lo que queda y el estado con texto", async () => {
    mockApi({ "GET /api/budgets": jsonResponse(200, aBudgetMonth()) });
    const { container } = renderWithProviders(<BudgetsPage />, { route: "/budgets" });

    expect(await screen.findByText("Supermercado")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Presupuestos" })).toBeInTheDocument();
    expect(
      within(screen.getByRole("group", { name: "Mes" })).getByText("noviembre de 2026"),
    ).toBeInTheDocument();
    expect(screen.getByText(/con el dólar MEP de cada día/)).toBeInTheDocument();

    // Ordenadas por el nombre que se ve.
    const names = screen
      .getAllByRole("listitem")
      .map((item) => item.querySelector("p")?.textContent);
    expect(names).toEqual(["Alquiler", "Supermercado"]);

    const food = rowOf("Supermercado");
    expect(within(food).getByText("Cerca del tope")).toBeInTheDocument();
    const meter = within(food).getByRole("meter", {
      name: /Gastaste \$\s245\.000,00 de \$\s300\.000,00/,
    });
    expect(meter).toHaveAttribute("aria-valuetext", "82% del tope");
    expect(food).toHaveTextContent(/Quedan \$\s55\.000,00/);
    expect(food).toHaveTextContent("Desde septiembre de 2026");

    const rent = rowOf("Alquiler");
    expect(within(rent).getByText("Llegaste al tope")).toBeInTheDocument();
    // El signo se dice con palabras, no con un menos ni solo con el color.
    expect(rent).toHaveTextContent(/Te pasaste por US\$\s12,50/);
    expect(within(rent).getByRole("meter")).toHaveAttribute("aria-valuetext", "103% del tope");
    expect(rent).toHaveTextContent(/Sin contar .*0,00150000.*: no tiene cotización/);

    await expectNoA11yViolations(container);
  });

  it("sin presupuestos invita a crear el primero", async () => {
    mockApi({ "GET /api/budgets": jsonResponse(200, aBudgetMonth({ budgets: [] })) });
    renderWithProviders(<BudgetsPage />, { route: "/budgets" });

    expect(await screen.findByText("Todavía no tenés presupuestos")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nuevo presupuesto" })).toHaveAttribute(
      "href",
      "/budgets/new",
    );
  });

  it("un mes pasado se lee de la URL y no se puede cambiar", async () => {
    const fetchMock = mockApi({
      "GET /api/budgets?month=2026-09": jsonResponse(
        200,
        aBudgetMonth({ month: "2026-09", budgets: [aBudget()] }),
      ),
    });
    renderWithProviders(<BudgetsPage />, { route: "/budgets?month=2026-09" });

    expect(await screen.findByText("Supermercado")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/budgets?month=2026-09", expect.anything());
    expect(screen.getByText(/Los cambios valen desde el mes en curso/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Nuevo presupuesto" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Quitar/ })).not.toBeInTheDocument();
  });

  it("un mes que todavía no empezó en la URL se ignora", async () => {
    const fetchMock = mockApi({ "GET /api/budgets": jsonResponse(200, aBudgetMonth()) });
    renderWithProviders(<BudgetsPage />, { route: "/budgets?month=2027-01" });

    expect(await screen.findByText("Supermercado")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/budgets", expect.anything());
  });

  it("se mueve al mes anterior, y al siguiente solo hasta el actual", async () => {
    const fetchMock = mockApi({
      "GET /api/budgets": jsonResponse(200, aBudgetMonth()),
      "GET /api/budgets?month=2026-10": jsonResponse(200, aBudgetMonth({ month: "2026-10" })),
    });
    renderWithProviders(<BudgetsPage />, { route: "/budgets" });
    const user = userEvent.setup();
    await screen.findByText("Supermercado");

    expect(screen.getByRole("button", { name: "Mes siguiente" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Mes anterior" }));

    const months = screen.getByRole("group", { name: "Mes" });
    expect(await within(months).findByText("octubre de 2026")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/budgets?month=2026-10", expect.anything());
    expect(screen.getByRole("button", { name: "Mes siguiente" })).toBeEnabled();
  });

  it("quitar no pregunta: avisa y deja deshacer con el mismo tope", async () => {
    const fetchMock = mockApi({
      "GET /api/budgets": jsonResponse(200, aBudgetMonth()),
      [`DELETE /api/budgets/${EXPENSE_CATEGORY.id}`]: new Response(null, { status: 204 }),
      [`PUT /api/budgets/${EXPENSE_CATEGORY.id}`]: jsonResponse(200, {}),
    });
    renderWithProviders(<BudgetsPage />, { route: "/budgets" });
    const user = userEvent.setup();
    await screen.findByText("Supermercado");

    await user.click(screen.getByRole("button", { name: "Quitar el presupuesto de Supermercado" }));
    expect(await screen.findByText("Quitaste el presupuesto de Supermercado.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Deshacer" }));

    const body = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")?.[1]?.body;
    expect(typeof body === "string" ? JSON.parse(body) : null).toEqual({
      amount: "300000.00",
      currency: "ARS",
    });
  });

  it("si no carga, lo dice y deja reintentar", async () => {
    mockApi({ "GET /api/budgets": jsonResponse(500, { code: "INTERNAL" }) });
    renderWithProviders(<BudgetsPage />, { route: "/budgets" });

    expect(await screen.findByText("No pudimos cargar los presupuestos.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("en inglés, el texto y los montos cambian de idioma", async () => {
    const { default: i18n } = await import("../../i18n");
    await i18n.changeLanguage("en");
    mockApi({ "GET /api/budgets": jsonResponse(200, aBudgetMonth()) });
    renderWithProviders(<BudgetsPage />, { route: "/budgets" });

    expect(await screen.findByRole("heading", { level: 1, name: "Budgets" })).toBeInTheDocument();
    await screen.findByText("Groceries");
    const food = rowOf("Groceries");
    expect(within(food).getByText("Close to the limit")).toBeInTheDocument();
    expect(food).toHaveTextContent(/55,000\.00 left/);
  });
});
