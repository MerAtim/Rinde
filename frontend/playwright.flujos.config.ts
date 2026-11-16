import { defineConfig, devices } from "@playwright/test";

/**
 * Los flujos críticos, de punta a punta, contra el entorno completo.
 *
 * A diferencia de las pruebas de maquetado (playwright.config.ts), acá no hay
 * nada simulado: el navegador habla con nginx, la API y PostgreSQL de
 * `docker compose`, con contraseñas hasheadas de verdad y la cookie de sesión
 * real (ADR-0013, decisión 3). Por eso no levanta ningún servidor: el entorno
 * ya tiene que estar arriba.
 *
 * La dirección se cambia con RINDE_FLUJOS_URL; por defecto, la del compose.
 */
const BASE_URL = process.env.RINDE_FLUJOS_URL ?? "http://127.0.0.1:8080";

export default defineConfig({
  testDir: "./e2e/flujos",
  // De a uno: el registro y la demo tienen límite por dirección de origen, y
  // todas las pruebas salen de la misma. En paralelo, un reintento podría
  // chocar contra ese límite y fallar por algo que no es un error.
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: {
    baseURL: BASE_URL,
    locale: "es-AR",
    timezoneId: "America/Argentina/Buenos_Aires",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
