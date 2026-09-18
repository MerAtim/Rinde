import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import type { Account } from "./api";
import { anAccount } from "./fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };
const ACCOUNT = anAccount();
const DETAIL = `/api/accounts/${ACCOUNT.id}`;
const ROUTE = `/accounts/${ACCOUNT.id}`;

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
    mockApi({ ...SESSION, [`GET ${DETAIL}`]: jsonResponse(200, ACCOUNT) });
    const { container } = renderWithProviders(<App />, { route: ROUTE });

    await screen.findByRole("heading", { name: "Galicia sueldo" });

    await expectNoA11yViolations(container);
  });
});
