import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { isLanguage, type Language } from "./index";

// El español es el de Argentina: punto para miles, coma para decimales (docs/design-system.md).
const LOCALE_BY_LANGUAGE: Record<Language, string> = {
  es: "es-AR",
  en: "en-US",
};

/** El locale de `Intl` que corresponde al idioma elegido. */
export function useLocale(): string {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? null;
  return isLanguage(language) ? LOCALE_BY_LANGUAGE[language] : LOCALE_BY_LANGUAGE.es;
}

/** Formatea una fecha ISO del servidor como "17 de septiembre de 2026". */
export function useDateFormatter(): (iso: string) => string {
  const locale = useLocale();
  return useMemo(() => {
    const formatter = new Intl.DateTimeFormat(locale, { dateStyle: "long" });
    return (iso: string) => formatter.format(new Date(iso));
  }, [locale]);
}

// Bitcoin admite 8 decimales (el satoshi); pesos y dólares, 2.
const FRACTION_DIGITS: Record<string, number> = { ARS: 2, USD: 2, BTC: 8 };
const CURRENCIES = Object.keys(FRACTION_DIGITS);

/**
 * `Intl.NumberFormat` acepta un string decimal desde ES2023, pero su tipo en
 * TypeScript todavía dice `number`. Se declara acá, en un solo lugar, en vez de
 * convertir el monto a número: esa conversión es la que pierde centavos.
 */
interface DecimalStringFormat {
  format(value: string): string;
}

function formatterFor(locale: string, currency: string): DecimalStringFormat {
  const digits = FRACTION_DIGITS[currency] ?? 2;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }) as unknown as DecimalStringFormat;
}

/** Formatea un monto que viene del servidor como string decimal (ADR-0002). */
export function useMoneyFormatter(): (amount: string, currency: string) => string {
  const locale = useLocale();
  return useMemo(() => {
    const formatters = new Map(
      CURRENCIES.map((currency) => [currency, formatterFor(locale, currency)]),
    );
    return (amount: string, currency: string) =>
      (formatters.get(currency) ?? formatterFor(locale, currency)).format(amount);
  }, [locale]);
}

/** La fecha de valor de un movimiento: "11 de septiembre", sin el año si es este. */
export function useShortDateFormatter(): (iso: string) => string {
  const locale = useLocale();
  return useMemo(() => {
    const formatter = new Intl.DateTimeFormat(locale, { day: "numeric", month: "long" });
    const withYear = new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
    return (iso: string) => {
      // Una fecha sin hora se interpreta en UTC: se arma local para no correr un día.
      const [year, month, day] = iso.split("-").map(Number);
      const date = new Date(year ?? 0, (month ?? 1) - 1, day ?? 1);
      const isThisYear = date.getFullYear() === new Date().getFullYear();
      return (isThisYear ? formatter : withYear).format(date);
    };
  }, [locale]);
}
