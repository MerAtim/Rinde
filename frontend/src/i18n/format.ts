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
