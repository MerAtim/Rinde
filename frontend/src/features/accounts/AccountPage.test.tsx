import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { aTransfer } from "../transfers/fixtures";
import { aBalance, aHistoryPage, aTransaction, EXPENSE_CATEGORY } from "../transactions/fixtures";
import type { Account } from "./api";
import { anAccount } from "./fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };
const ACCOUNT = anAccount();
const DETAIL = `/api/accounts/${ACCOUNT.id}`;
const ROUTE = `/accounts/${ACCOUNT.id}`;
const BALANCES = "GET /api/transactions/balances";
/** El detalle pide los últimos cinco movimientos de esta cuenta. */
const MOVEMENTS = `GET /api/history?account_id=${ACCOUNT.id}&limit=5`;
const CATEGORIES = "GET /api/categories";

/** Una respuesta que el test libera cuando quiere, para ver la pantalla mientras espera. */
function deferred() {
  let release: (response: Response) => void = () => undefined;
  const promise = new Promise<Response>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

async function typeName(name: string) {
  const user = userEvent.setup();
  const field = await screen.findByLabelText("Nombre");
  await user.clear(field);
  await user.type(field, name);
  await user.click(screen.getByRole("button", { name: "Guardar el nombre" }));
}

describe("Detalle de una cuenta", () => {
  it("muestra el tipo, la moneda y la fecha de apertura con el formato local", async () => {
    mockApi({ ...SESSION, [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT) });
    renderWithProviders(<App />, { route: ROUTE });

    expect(await screen.findByRole("heading", { name: "Galicia sueldo" })).toBeInTheDocument();
    expect(screen.getByText("Banco · Pesos argentinos (ARS)")).toBeInTheDocument();
    expect(screen.getByText("Abierta el 17 de septiembre de 2026")).toBeInTheDocument();
  });

  it("muestra el saldo y los últimos movimientos, sin repetir la cuenta", async () => {
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [BALANCES]: jsonResponse(200, [aBalance()]),
      [MOVEMENTS]: jsonResponse(200, aHistoryPage([aTransaction()])),
      [CATEGORIES]: jsonResponse(200, [EXPENSE_CATEGORY]),
    });
    renderWithProviders(<App />, { route: ROUTE });

    const money = await screen.findByRole("region", { name: "Saldo" });
    expect(await within(money).findByText(/84\.699,50/)).toBeInTheDocument();

    const movement = await screen.findByText("Coto");
    const row = movement.closest("li");
    expect(row).toHaveTextContent("15.300,50");
    // Ya se sabe de qué cuenta es: la fila no repite el nombre.
    expect(row).not.toHaveTextContent("Galicia sueldo");

    expect(screen.getByRole("link", { name: "Ver todos los movimientos" })).toHaveAttribute(
      "href",
      `/transactions?account=${ACCOUNT.id}`,
    );
    expect(screen.getByRole("link", { name: "Registrar movimiento" })).toHaveAttribute(
      "href",
      `/transactions/new?account=${ACCOUNT.id}`,
    );
  });

  it("sin movimientos, el saldo es cero y no ofrece verlos todos", async () => {
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [BALANCES]: jsonResponse(200, []),
      [MOVEMENTS]: jsonResponse(200, aHistoryPage([])),
      [CATEGORIES]: jsonResponse(200, []),
    });
    renderWithProviders(<App />, { route: ROUTE });

    expect(
      await screen.findByText("Todavía no registraste movimientos en esta cuenta."),
    ).toBeInTheDocument();
    const money = screen.getByRole("region", { name: "Saldo" });
    expect(within(money).getByText(/0,00/)).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Ver todos los movimientos" }),
    ).not.toBeInTheDocument();
    // El acceso para registrar el primero sigue estando.
    expect(screen.getByRole("link", { name: "Registrar movimiento" })).toBeInTheDocument();
  });

  it("una cuenta archivada muestra su saldo pero no deja registrar", async () => {
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, { ...ACCOUNT, archived_at: "2026-09-18T10:00:00Z" }),
      [BALANCES]: jsonResponse(200, [aBalance()]),
      [MOVEMENTS]: jsonResponse(200, aHistoryPage([aTransaction()])),
      [CATEGORIES]: jsonResponse(200, [EXPENSE_CATEGORY]),
    });
    renderWithProviders(<App />, { route: ROUTE });

    const money = await screen.findByRole("region", { name: "Saldo" });
    expect(await within(money).findByText(/84\.699,50/)).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: "Ver todos los movimientos" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Registrar movimiento" })).not.toBeInTheDocument();
  });

  it("las transferencias aparecen en la misma lista, vistas desde esta cuenta", async () => {
    const OTRA = anAccount({ id: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d", name: "Efectivo" });
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [BALANCES]: jsonResponse(200, []),
      [CATEGORIES]: jsonResponse(200, []),
      "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT, OTRA]),
      [MOVEMENTS]: jsonResponse(200, aHistoryPage([aTransfer()])),
    });
    renderWithProviders(<App />, { route: ROUTE });

    const fila = (await screen.findByText("Hacia Efectivo")).closest("li");
    // Desde esta cuenta la plata salió: monto con signo y la palabra para el
    // lector de pantalla. Desde la otra cuenta la misma fila se ve al revés.
    expect(within(fila as HTMLElement).getByText("Gasto")).toBeInTheDocument();
    expect(fila).toHaveTextContent("50.000,00");
  });

  it("ofrece transferir desde la cuenta", async () => {
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [BALANCES]: jsonResponse(200, []),
      [CATEGORIES]: jsonResponse(200, []),
      "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]),
      [MOVEMENTS]: jsonResponse(200, aHistoryPage([])),
    });
    renderWithProviders(<App />, { route: ROUTE });

    expect(await screen.findByRole("link", { name: "Transferir" })).toHaveAttribute(
      "href",
      `/transfers/new?account=${ACCOUNT.id}`,
    );
  });

  it("renombra al instante, sin esperar al servidor", async () => {
    let current: Account = ACCOUNT;
    const pending = deferred();
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: () => jsonResponse(200, current),
      [`PATCH ${DETAIL}`]: () => pending.promise,
    });
    renderWithProviders(<App />, { route: ROUTE });

    await typeName("Galicia");

    // El servidor todavía no respondió y el nombre ya cambió.
    expect(screen.getByRole("heading", { level: 1, name: "Galicia" })).toBeInTheDocument();

    current = { ...ACCOUNT, name: "Galicia" };
    pending.release(jsonResponse(200, current));
    expect(await screen.findByText("Guardamos el nombre nuevo.")).toBeInTheDocument();
  });

  it("si el servidor rechaza el nombre, vuelve al anterior y dice cómo corregirlo", async () => {
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [`PATCH ${DETAIL}`]: jsonResponse(422, { code: "ACCOUNT_NAME_INVALID" }),
    });
    renderWithProviders(<App />, { route: ROUTE });

    await typeName("Galicia");

    expect(
      await screen.findByText("Usá hasta 60 caracteres, sin caracteres invisibles."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Galicia sueldo" })).toBeInTheDocument();
  });

  it("archiva después de confirmar y vuelve a la lista", async () => {
    let archived = false;
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [`POST ${DETAIL}/archive`]: () => {
        archived = true;
        return jsonResponse(200, { ...ACCOUNT, archived_at: "2026-09-18T10:00:00Z" });
      },
      "GET /api/accounts": () => jsonResponse(200, archived ? [] : [ACCOUNT]),
    });
    renderWithProviders(<App />, { route: ROUTE });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Archivar la cuenta" }));
    const dialog = await screen.findByRole("alertdialog", { name: "¿Archivar «Galicia sueldo»?" });
    expect(archived).toBe(false);
    await user.click(screen.getByRole("button", { name: "Archivar" }));

    expect(
      await screen.findByRole("heading", { name: "Todavía no tenés cuentas" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Archivaste la cuenta «Galicia sueldo».")).toBeInTheDocument();
    expect(dialog).not.toBeInTheDocument();
  });

  it("cancelar el diálogo no archiva", async () => {
    let archived = false;
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [`POST ${DETAIL}/archive`]: () => {
        archived = true;
        return jsonResponse(200, ACCOUNT);
      },
    });
    renderWithProviders(<App />, { route: ROUTE });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Archivar la cuenta" }));
    await user.click(await screen.findByRole("button", { name: "Cancelar" }));

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(archived).toBe(false);
  });

  it("una cuenta archivada no se puede renombrar ni archivar otra vez", async () => {
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, { ...ACCOUNT, archived_at: "2026-09-18T10:00:00Z" }),
    });
    renderWithProviders(<App />, { route: ROUTE });

    expect(await screen.findByText("Archivada el 18 de septiembre de 2026")).toBeInTheDocument();
    expect(screen.queryByLabelText("Nombre")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archivar la cuenta" })).not.toBeInTheDocument();
  });

  it.each([
    ["ajena o inexistente", 404, { code: "ACCOUNT_NOT_FOUND" }],
    ["con un identificador mal formado", 422, { detail: [] }],
  ])("una cuenta %s se informa como no encontrada", async (_case, status, body) => {
    mockApi({ ...SESSION, [`GET ${DETAIL}`]: jsonResponse(status, body) });
    renderWithProviders(<App />, { route: ROUTE });

    expect(
      await screen.findByRole("heading", { name: "No encontramos esta cuenta" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver a cuentas" })).toHaveAttribute(
      "href",
      "/accounts",
    );
  });

  it("si falla la carga por otro motivo, permite reintentar", async () => {
    mockApi({ ...SESSION, [`GET ${DETAIL}`]: jsonResponse(503) });
    renderWithProviders(<App />, { route: ROUTE });

    expect(await screen.findByRole("alert")).toHaveTextContent("No pudimos cargar la cuenta.");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi({
      ...SESSION,
      [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT),
      [BALANCES]: jsonResponse(200, [aBalance()]),
      [MOVEMENTS]: jsonResponse(200, aHistoryPage([aTransaction()])),
      [CATEGORIES]: jsonResponse(200, [EXPENSE_CATEGORY]),
    });
    const { container } = renderWithProviders(<App />, { route: ROUTE });

    await screen.findByRole("heading", { name: "Galicia sueldo" });
    await screen.findByText("Coto");

    await expectNoA11yViolations(container);
  });
});
