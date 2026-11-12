import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { EXPENSE_CATEGORY, INCOME_CATEGORY } from "../transactions/fixtures";
import { BudgetFormPage } from "./BudgetFormPage";
import { aBudget, aBudgetMonth, OWN_CATEGORY, RENT_CATEGORY } from "./fixtures";

const CATEGORIES = [EXPENSE_CATEGORY, RENT_CATEGORY, OWN_CATEGORY, INCOME_CATEGORY];
// Supermercado ya tiene tope este mes.
const BUDGETS = aBudgetMonth({ budgets: [aBudget()] });

function routes(preferences = { reference_currency: "ARS", rate_type: "mep" }) {
  return {
    "GET /api/categories": jsonResponse(200, CATEGORIES),
    "GET /api/budgets": jsonResponse(200, BUDGETS),
    "GET /api/preferences": jsonResponse(200, preferences),
  };
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/budgets/new" element={<BudgetFormPage />} />
      <Route path="/budgets/:categoryId/edit" element={<BudgetFormPage />} />
      <Route path="/budgets" element={<p>Lista de presupuestos</p>} />
    </Routes>,
    { route },
  );
}

function bodyOf(fetchMock: ReturnType<typeof mockApi>, method: string): unknown {
  const body = fetchMock.mock.calls.find(([, init]) => init?.method === method)?.[1]?.body;
  return typeof body === "string" ? (JSON.parse(body) as unknown) : undefined;
}

describe("BudgetFormPage", () => {
  it("un tope nuevo: categorías de gasto sin tope, y la moneda de referencia por defecto", async () => {
    const fetchMock = mockApi({
      ...routes({ reference_currency: "USD", rate_type: "mep" }),
      [`PUT /api/budgets/${RENT_CATEGORY.id}`]: jsonResponse(200, {}),
    });
    const { container } = renderAt("/budgets/new");
    const user = userEvent.setup();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Nuevo presupuesto" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Categoría/ }));
    expect(await screen.findByRole("option", { name: "Alquiler" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Clases de tango" })).toBeInTheDocument();
    // La que ya tiene tope se cambia desde su fila; un ingreso no se presupuesta.
    expect(screen.queryByRole("option", { name: "Supermercado" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Sueldo" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "Alquiler" }));

    expect(screen.getByRole("radio", { name: "Dólares (USD)" })).toBeChecked();
    await user.type(screen.getByRole("textbox", { name: /Tope por mes/ }), "1.200,50");
    await expectNoA11yViolations(container);
    await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));

    expect(await screen.findByText("Lista de presupuestos")).toBeInTheDocument();
    expect(bodyOf(fetchMock, "PUT")).toEqual({ amount: "1200.50", currency: "USD" });
  });

  it("valida antes de enviar: categoría y un tope mayor que cero", async () => {
    const fetchMock = mockApi(routes());
    renderAt("/budgets/new");
    const user = userEvent.setup();
    const submit = await screen.findByRole("button", { name: "Guardar presupuesto" });

    await user.click(submit);
    expect(screen.getByRole("textbox", { name: /Tope por mes/ })).toHaveAccessibleDescription(
      /Escribí el tope/,
    );

    await user.type(screen.getByRole("textbox", { name: /Tope por mes/ }), "0,00");
    await user.click(submit);
    expect(screen.getByRole("textbox", { name: /Tope por mes/ })).toHaveAccessibleDescription(
      /mayor que cero/,
    );

    await user.clear(screen.getByRole("textbox", { name: /Tope por mes/ }));
    await user.type(screen.getByRole("textbox", { name: /Tope por mes/ }), "1000");
    await user.click(submit);
    expect(screen.getByRole("button", { name: /Categoría/ })).toHaveAccessibleDescription(
      /Elegí una categoría/,
    );
    expect(bodyOf(fetchMock, "PUT")).toBeUndefined();
  });

  it("cambiar un tope arranca con el guardado y muestra el error del servidor en su campo", async () => {
    const fetchMock = mockApi({
      ...routes({ reference_currency: "USD", rate_type: "mep" }),
      [`PUT /api/budgets/${EXPENSE_CATEGORY.id}`]: jsonResponse(422, {
        code: "AMOUNT_TOO_PRECISE",
      }),
    });
    renderAt(`/budgets/${EXPENSE_CATEGORY.id}/edit`);
    const user = userEvent.setup();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Tope de Supermercado" }),
    ).toBeInTheDocument();
    const amount = screen.getByRole("textbox", { name: /Tope por mes/ });
    expect(amount).toHaveValue("300000,00");
    // La moneda es la del tope guardado, no la de referencia.
    expect(screen.getByRole("radio", { name: "Pesos argentinos (ARS)" })).toBeChecked();
    expect(screen.queryByRole("button", { name: /Categoría/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Guardar presupuesto" }));

    expect(await screen.findByText("El tope admite hasta dos decimales.")).toBeInTheDocument();
    expect(bodyOf(fetchMock, "PUT")).toEqual({ amount: "300000.00", currency: "ARS" });
  });

  it("una categoría sin tope este mes no se puede editar", async () => {
    mockApi(routes());
    renderAt(`/budgets/${RENT_CATEGORY.id}/edit`);

    expect(
      await screen.findByText("Esta categoría no tiene presupuesto este mes."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("si todas las categorías de gasto ya tienen tope, lo dice", async () => {
    mockApi({
      ...routes(),
      "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY]),
    });
    renderAt("/budgets/new");

    expect(
      await screen.findByText(/Todas tus categorías de gasto ya tienen presupuesto/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
