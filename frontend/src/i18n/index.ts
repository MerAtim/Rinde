import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import es from "./locales/es.json";

export const SUPPORTED_LANGUAGES = ["es", "en"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

const STORAGE_KEY = "rinde.language";

export function isLanguage(value: string | null): value is Language {
  return SUPPORTED_LANGUAGES.some((language) => language === value);
}

function readStoredLanguage(): Language | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isLanguage(stored) ? stored : null;
  } catch {
    return null;
  }
}

function detectLanguage(): Language {
  const browserPrefersEnglish = navigator.language.toLowerCase().startsWith("en");
  return readStoredLanguage() ?? (browserPrefersEnglish ? "en" : "es");
}

i18n.on("languageChanged", (language: string) => {
  document.documentElement.lang = language;
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // Almacenamiento no disponible (modo privado): el idioma dura lo que dura la sesión.
  }
});

void i18n.use(initReactI18next).init({
  // `satisfies` obliga a que el inglés tenga todas las claves del español.
  resources: { es: { translation: es }, en: { translation: en satisfies typeof es } },
  lng: detectLanguage(),
  fallbackLng: "es",
  supportedLngs: SUPPORTED_LANGUAGES,
  initAsync: false,
  interpolation: { escapeValue: false }, // React ya escapa el contenido
});

export default i18n;
