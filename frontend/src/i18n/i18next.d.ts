import "i18next";

import type es from "./locales/es.json";

// Claves de traducción tipadas: t("clave.inexistente") no compila.
declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "translation";
    resources: { translation: typeof es };
  }
}
