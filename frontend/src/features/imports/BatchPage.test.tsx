import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { announcementFrom } from "../../shared/navigation/announcement";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import { EXPENSE_CATEGORY, INCOME_CATEGORY } from "../transactions/fixtures";
import { BatchPage } from "./BatchPage";
import { aBatch, BATCH_ID } from "./fixtures";

const FOOD = {
  ...EXPENSE_CATEGORY,
  id: "99999999-9999-4999-8999-999999999999",
  name: "Kiosco",
  slug: null,
};

function Landing() {
  const location = useLocation();
  return <p>Movimientos: {announcementFrom(location.state)}</p>;
}

function routes(batch = aBatch()) {
  return {
    [`GET /api/imports/${BATCH_ID}`]: jsonResponse(200, batch),
    "GET /api/categories": jsonResponse(200, [EXPENSE_CATEGORY, INCOME_CATEGORY, FOOD]),
    "GET /api/accounts?include_archived=true": jsonResponse(200, [anAccount()]),
  };
}

function renderBatch() {
  return renderWithProviders(
    <Routes>
      <Route path="/imports/:batchId" element={<BatchPage />} />
      <Route path="/transactions" element={<Landing />} />
      <Route path="/transactions/import" element={<Landing />} />
    </Routes>,
    { route: `/imports/${BATCH_ID}` },
  );
}

function bodyOf(fetchMock: ReturnType<typeof mockApi>): unknown {
  const body = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.body;
  return typeof body === "string" ? (JSON.parse(body) as unknown) : undefined;
}

function rowOf(description: string): HTMLElement {
  const row = screen.getByText(description).closest("li");
  if (!row) {
    throw new Error(`no hay fila para ${description}`);
  }
  return row;
}

describe("BatchPage", () => {
  it("muestra el resumen, las líneas ilegibles y qué entra por defecto", async () => {
    mockApi(routes());
    const { container } = renderBatch();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Revisá antes de importar" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/octubre\.csv, en la cuenta Galicia sueldo/),
    ).toBeInTheDocument();
    const summary = screen.getByRole("list", { name: "Resumen del archivo" });
    expect(summary).toHaveTextContent("2 nuevos");
    expect(summary).toHaveTextContent("1 ya importado");
    expect(summary).toHaveTextContent("1 posible duplicado");
    expect(summary).toHaveTextContent("1 línea sin leer");
    expect(screen.getByText("Línea 6: la fecha no se entiende.")).toBeInTheDocument();

    // Las nuevas entran; un posible duplicado, no; un duplicado no se puede elegir.
    expect(within(rowOf("COTO SUC 123")).getByRole("checkbox")).toBeChecked();
    expect(within(rowOf("HABERES")).getByRole("checkbox")).toBeChecked();
    expect(within(rowOf("CAFE")).getByRole("checkbox")).not.toBeChecked();
    expect(within(rowOf("CAFE")).getByText("Posible duplicado")).toBeInTheDocument();
    expect(within(rowOf("YA ESTABA")).getByRole("checkbox")).toBeDisabled();
    // Una fecha sin hora no se corre un día por la zona horaria.
    expect(rowOf("COTO SUC 123")).toHaveTextContent("3 de noviembre");
    // El signo se dice con palabras, además del color.
    expect(rowOf("COTO SUC 123")).toHaveTextContent(/Gasto.*−\$\s1\.500,50/);
    expect(rowOf("HABERES")).toHaveTextContent(/Ingreso.*\+\$\s250\.000,00/);
    expect(screen.getByRole("button", { name: "Importar 2 movimientos" })).toBeEnabled();
    await expectNoA11yViolations(container);
  });

  it("confirma lo elegido, con sus categorías, y vuelve a movimientos con un aviso", async () => {
    const fetchMock = mockApi({
      ...routes(),
      [`POST /api/imports/${BATCH_ID}/confirm`]: jsonResponse(200, { imported: 2, skipped: 0 }),
    });
    renderBatch();
    const user = userEvent.setup();

    await screen.findByText("COTO SUC 123");
    await user.click(
      within(rowOf("COTO SUC 123")).getByRole("button", { name: /Categoría de COTO SUC 123/ }),
    );
    await user.click(await screen.findByRole("option", { name: "Kiosco" }));
    await user.click(within(rowOf("HABERES")).getByRole("checkbox"));
    await user.click(within(rowOf("CAFE")).getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Importar 2 movimientos" }));

    expect(await screen.findByText("Movimientos: Importaste 2 movimientos.")).toBeInTheDocument();
    expect(bodyOf(fetchMock)).toEqual({
      lines: [
        { number: 2, category_id: FOOD.id },
        { number: 5, category_id: EXPENSE_CATEGORY.id },
      ],
    });
  });

  it("sin nada elegido no se puede importar", async () => {
    mockApi(routes());
    renderBatch();
    const user = userEvent.setup();

    await screen.findByText("COTO SUC 123");
    await user.click(within(rowOf("COTO SUC 123")).getByRole("checkbox"));
    await user.click(within(rowOf("HABERES")).getByRole("checkbox"));

    expect(screen.getByRole("button", { name: "Importar 0 movimientos" })).toBeDisabled();
  });

  it("muestra el error del servidor y deja reintentar", async () => {
    mockApi({
      ...routes(),
      [`POST /api/imports/${BATCH_ID}/confirm`]: jsonResponse(422, {
        code: "CATEGORY_KIND_MISMATCH",
      }),
    });
    renderBatch();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Importar 2 movimientos" }));

    expect(
      await screen.findByText(
        "Un gasto necesita una categoría de gastos, y un ingreso, una de ingresos.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importar 2 movimientos" })).toBeEnabled();
  });

  it("descartar vuelve a importar con un aviso", async () => {
    mockApi({
      ...routes(),
      [`DELETE /api/imports/${BATCH_ID}`]: new Response(null, { status: 204 }),
    });
    renderBatch();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Descartar" }));

    expect(
      await screen.findByText("Movimientos: Descartaste la importación de octubre.csv."),
    ).toBeInTheDocument();
  });

  it("un lote vencido lo dice y no muestra nada más", async () => {
    mockApi({
      ...routes(),
      [`GET /api/imports/${BATCH_ID}`]: jsonResponse(404, { code: "IMPORT_BATCH_NOT_FOUND" }),
    });
    renderBatch();

    expect(await screen.findByText(/vence a las 24 horas/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Importar/ })).not.toBeInTheDocument();
  });

  it("un lote ya confirmado no se vuelve a ofrecer", async () => {
    mockApi(routes(aBatch({ confirmed: true })));
    renderBatch();

    expect(await screen.findByText("Este archivo ya se importó.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver movimientos" })).toHaveAttribute(
      "href",
      "/transactions",
    );
  });
});
