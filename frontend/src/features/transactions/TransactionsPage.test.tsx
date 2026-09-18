import { screen, within } from "@testing-library/react";
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
const CATEGORIES = [EXPENSE_CATEGORY, INCOME_CATEGORY];

const BASE = {
  ...SESSION,
  "GET /api/categories": jsonResponse(200, CATEGORIES),
  "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
  "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
  "GET /api/transactions/balances": jsonResponse(200, []),
};

describe("Movimientos", () => {
  it("lista los movimientos con su fecha, su categoría y su monto", async () => {
    mockApi({
      ...BASE,
      "GET /api/transactions": jsonResponse(200, aPage([aTransaction()])),
    });
    renderWithProviders(<App />, { route: "/transactions" });

    const row = await screen.findByText("Coto");
    const item = row.closest("li");
    expect(item).not.toBeNull();
    expect(item).toHaveTextContent("18 de septiembre");
    expect(item).toHaveTextContent("Supermercado");
    // Gasto: signo menos y la palabra para el lector de pantalla.
    expect(within(item as HTMLElement).getByText("Gasto")).toBeInTheDocument();
    expect(item).toHaveTextContent("15.300,50");
  });

  it("sin movimientos explica qué hacer", async () => {
    mockApi({ ...BASE, "GET /api/transactions": jsonResponse(200, aPage([])) });
    renderWithProviders(<App />, { route: "/transactions" });

    expect(
      await screen.findByRole("heading", { name: "Todavía no registraste movimientos" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Registrar el primero" })).toHaveAttribute(
      "href",
      "/transactions/new",
    );
  });

  it("borra sin preguntar y deja deshacer", async () => {
    const movement = aTransaction();
    let alive = true;
    mockApi({
      ...BASE,
      "GET /api/transactions": () => jsonResponse(200, aPage(alive ? [movement] : [])),
      [`DELETE /api/transactions/${movement.id}`]: () => {
        alive = false;
        return jsonResponse(200, { ...movement, deleted_at: "2026-09-18T14:00:00Z" });
      },
      [`POST /api/transactions/${movement.id}/restore`]: () => {
        alive = true;
        return jsonResponse(200, movement);
      },
    });
    renderWithProviders(<App />, { route: "/transactions" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /Borrar: Coto/ }));

    // El marco tiene su propia región de avisos: se busca el snackbar por su texto.
    const snackbar = (await screen.findByText("Borraste el movimiento.")).closest("[role=status]");
    expect(snackbar).not.toBeNull();
    await user.click(within(snackbar as HTMLElement).getByRole("button", { name: "Deshacer" }));

    expect(await screen.findByText("Coto")).toBeInTheDocument();
  });

  it("trae la página siguiente sin repetir filas", async () => {
    const first = aTransaction({ description: "Primero" });
    const second = aTransaction({
      id: "9f1a2b3c-4d5e-4f60-8a1b-2c3d4e5f6a7c",
      description: "Segundo",
    });
    mockApi({
      ...BASE,
      "GET /api/transactions": jsonResponse(200, aPage([first], "cursor-2")),
      "GET /api/transactions?cursor=cursor-2": jsonResponse(200, aPage([second])),
    });
    renderWithProviders(<App />, { route: "/transactions" });
    const user = userEvent.setup();

    await screen.findByText("Primero");
    await user.click(screen.getByRole("button", { name: "Ver más" }));

    expect(await screen.findByText("Segundo")).toBeInTheDocument();
    expect(screen.getByText("Primero")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ver más" })).not.toBeInTheDocument();
  });

  it("si falla la carga, lo dice y permite reintentar", async () => {
    mockApi({ ...BASE, "GET /api/transactions": jsonResponse(500) });
    renderWithProviders(<App />, { route: "/transactions" });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Algo salió mal. Probá de nuevo en un momento.",
    );
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi({
      ...BASE,
      "GET /api/transactions": jsonResponse(200, aPage([aTransaction()])),
    });
    const { container } = renderWithProviders(<App />, { route: "/transactions" });

    await screen.findByText("Coto");

    await expectNoA11yViolations(container);
  });
});
