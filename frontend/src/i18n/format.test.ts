import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import i18n from "./index";
import {
  useAxisMoneyFormatter,
  useDateFormatter,
  useMoneyFormatter,
  useMonthFormatter,
  useRateFormatter,
  useShortDateFormatter,
} from "./format";

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

  it("muestra una cotización como cifra sola, con dos decimales", () => {
    const { result } = renderHook(() => useRateFormatter());

    expect(result.current("1587.90000000")).toBe("1.587,90");
    expect(result.current("1665.22900000")).toBe("1.665,23");
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

describe("Meses y ejes", () => {
  it("nombra un mes sin correrse al anterior por la zona horaria", () => {
    const { result } = renderHook(() => useMonthFormatter());

    expect(result.current("2026-06", "long")).toBe("junio de 2026");
    expect(result.current("2026-01", "short")).toMatch(/^ene/);
    expect(result.current("2025-12", "short-with-year")).toMatch(/^dic.*25$/);
  });

  it("en inglés, con el formato de Estados Unidos", async () => {
    await i18n.changeLanguage("en");
    const { result } = renderHook(() => useMonthFormatter());

    expect(result.current("2026-06", "long")).toBe("June 2026");
  });

  it("abrevia las marcas de un eje de dinero y mantiene la moneda", () => {
    const { result } = renderHook(() => useAxisMoneyFormatter());

    expect(plain(result.current(1_200_000, "ARS"))).toMatch(/^\$\s?1,2\s?M$/);
    expect(plain(result.current(-2500, "USD"))).toContain("US$");
  });
});
