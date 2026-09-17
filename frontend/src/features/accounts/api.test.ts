import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { jsonResponse } from "../../test/render";
import { archiveAccount, fetchAccounts, openAccount, renameAccount } from "./api";
import { errorCodeOf, validateName, validateNewAccount } from "./errors";
import { anAccount } from "./fixtures";

describe("API de cuentas", () => {
  it("pide las archivadas solo cuando se lo indica", async () => {
    const fetchMock = mockApi({
      "GET /api/accounts": jsonResponse(200, []),
      "GET /api/accounts?include_archived=true": jsonResponse(200, [anAccount()]),
    });

    await expect(fetchAccounts(false, new AbortController().signal)).resolves.toEqual([]);
    await expect(fetchAccounts(true, new AbortController().signal)).resolves.toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("abre una cuenta con el encabezado CSRF y los datos como JSON", async () => {
    const fetchMock = mockApi({ "POST /api/accounts": jsonResponse(201, anAccount()) });

    await openAccount({ name: "Galicia sueldo", kind: "bank", currency: "ARS" });

    const [, init] = fetchMock.mock.calls[0] ?? [];
    expect(init?.headers).toMatchObject({ "X-Requested-With": "rinde" });
    expect(init?.body).toBe(
      JSON.stringify({ name: "Galicia sueldo", kind: "bank", currency: "ARS" }),
    );
  });

  it("renombra y archiva con el encabezado CSRF", async () => {
    const account = anAccount();
    const fetchMock = mockApi({
      [`PATCH /api/accounts/${account.id}`]: jsonResponse(200, account),
      [`POST /api/accounts/${account.id}/archive`]: jsonResponse(200, account),
    });

    await renameAccount(account.id, "Galicia");
    await archiveAccount(account.id);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.headers).toMatchObject({ "X-Requested-With": "rinde" });
    }
  });

  it("convierte el código de la API en un error tipado", async () => {
    mockApi({ "POST /api/accounts": jsonResponse(422, { code: "ACCOUNT_NAME_INVALID" }) });

    const error: unknown = await openAccount({ name: "x", kind: "cash", currency: "ARS" }).catch(
      (reason: unknown) => reason,
    );

    expect(errorCodeOf(error)).toBe("ACCOUNT_NAME_INVALID");
  });

  it("no deja pasar sin traducción los códigos de otros módulos", async () => {
    mockApi({ "POST /api/accounts": jsonResponse(400, { code: "USERNAME_TAKEN" }) });

    const error: unknown = await openAccount({ name: "x", kind: "cash", currency: "ARS" }).catch(
      (reason: unknown) => reason,
    );

    expect(errorCodeOf(error)).toBe("UNKNOWN_ERROR");
  });
});

describe("Validación de cuentas", () => {
  it("exige un nombre con algo más que espacios", () => {
    expect(validateName("   ")).toBe("ACCOUNT_NAME_REQUIRED");
    expect(validateName(" Galicia ")).toBeNull();
  });

  it("cuenta el largo como el servidor: por puntos de código", () => {
    // Cada emoji ocupa dos unidades UTF-16, pero para el servidor es un solo carácter.
    expect(validateName("\u{1F4B5}".repeat(60))).toBeNull();
    expect(validateName("a".repeat(61))).toBe("ACCOUNT_NAME_INVALID");
  });

  it("solo admite Bitcoin en billeteras cripto", () => {
    expect(validateNewAccount("Lemon", "bank", "BTC")).toBe("ACCOUNT_CURRENCY_NOT_ALLOWED");
    expect(validateNewAccount("Lemon", "crypto_wallet", "BTC")).toBeNull();
  });
});
