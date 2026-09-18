import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import i18n from "./index";
import { useDateFormatter, useMoneyFormatter, useShortDateFormatter } from "./format";

/** Intl separa el símbolo con espacios duros: se normalizan para comparar. */
function plain(value: string): string {
  return value.replace(/[\u00a0\u202f]/g, " ");
}

describe("Formato", () => {
  it("usa el formato argentino: punto para miles y coma para decimales", () => {
    const { result } = renderHook(() => useMoneyFormatter());

    expect(plain(result.current("15300.50", "ARS"))).toBe("$ 15.300,50");
    expect(plain(result.current("1234567.89", "USD"))).toBe("US$ 1.234.567,89");
  });

  it("no pierde precisión con montos que no entran en un double", () => {
    const { result } = renderHook(() => useMoneyFormatter());

    // 9007199254740993 es el primer entero que un double ya no representa exacto.
    expect(plain(result.current("9007199254740993.01", "ARS"))).toContain(
      "9.007.199.254.740.993,01",
    );
    expect(plain(result.current("0.00000001", "BTC"))).toContain("0,00000001");
  });

  it("muestra la fecha de un movimiento sin correrla de día", () => {
    const { result } = renderHook(() => useShortDateFormatter());

    // Sin hora, una fecha ISO se interpreta en UTC: en Argentina sería el día anterior.
    expect(result.current("2026-09-01")).toBe("1 de septiembre");
  });

  it("acompaña al idioma elegido", async () => {
    await i18n.changeLanguage("en");
    const { result } = renderHook(() => useDateFormatter());

    expect(result.current("2026-09-17T13:00:00Z")).toContain("September");

    await i18n.changeLanguage("es");
  });
});
