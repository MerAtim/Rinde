import { describe, expect, it } from "vitest";

import { dashboardQuery, DEFAULT_MONTHS, filtersFrom, firstMonth, withFilters } from "./period";

const ACCOUNT = "5c4b3a29-1807-4f6e-9d5c-4b3a29180706";

describe("filtros del dashboard en la URL", () => {
  it("sin parámetros, los últimos seis meses de todas las cuentas", () => {
    expect(filtersFrom(new URLSearchParams())).toEqual({ months: DEFAULT_MONTHS, accountId: "" });
  });

  it("lee el período y la cuenta", () => {
    const params = new URLSearchParams({ months: "12", account: ACCOUNT });
    expect(filtersFrom(params)).toEqual({ months: 12, accountId: ACCOUNT });
  });

  it.each(["0", "7", "abc", "1e1", "-6", "24.0x"])(
    "un período que no está en la lista (%s) vuelve al de siempre",
    (months) => {
      expect(filtersFrom(new URLSearchParams({ months })).months).toBe(DEFAULT_MONTHS);
    },
  );

  it("una cuenta que no es un identificador se ignora y no llega al servidor", () => {
    const params = new URLSearchParams({ account: "../accounts?x=1" });
    expect(filtersFrom(params).accountId).toBe("");
  });

  it("no escribe lo que vale lo de siempre y conserva los demás parámetros", () => {
    const params = new URLSearchParams({ months: "12", account: ACCOUNT, other: "1" });
    const updated = withFilters(params, { months: DEFAULT_MONTHS, accountId: "" });
    expect(updated.toString()).toBe("other=1");
  });

  it("escribe un período y una cuenta elegidos", () => {
    const updated = withFilters(new URLSearchParams(), { months: 3, accountId: ACCOUNT });
    expect(filtersFrom(updated)).toEqual({ months: 3, accountId: ACCOUNT });
  });
});

describe("primer mes del período", () => {
  it.each([
    ["2026-11", 6, "2026-06"],
    ["2026-11", 3, "2026-09"],
    ["2026-02", 3, "2025-12"],
    ["2026-11", 12, "2025-12"],
    ["2026-01", 24, "2024-02"],
    ["2026-12", 1, "2026-12"],
  ])("desde %s, %i meses empiezan en %s", (current, months, expected) => {
    expect(firstMonth(current, months)).toBe(expected);
  });
});

describe("lo que se le pide al servidor", () => {
  // 23:30 del 30 de noviembre en Buenos Aires: en UTC ya es diciembre.
  const NOW = new Date("2026-12-01T02:30:00Z");

  it("el período de siempre no se manda: lo decide el servidor", () => {
    expect(dashboardQuery({ months: DEFAULT_MONTHS, accountId: "" }, NOW)).toEqual({});
  });

  it("otro período cuenta desde el mes de Argentina, no desde el de UTC", () => {
    expect(dashboardQuery({ months: 3, accountId: ACCOUNT }, NOW)).toEqual({
      from: "2026-09",
      accountId: ACCOUNT,
    });
  });
});
