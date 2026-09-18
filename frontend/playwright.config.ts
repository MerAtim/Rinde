import { defineConfig, devices } from "@playwright/test";

/**
 * Pruebas de extremo a extremo en un navegador de verdad.
 *
 * Corren contra el build de producción servido por `vite preview`, no contra el
 * servidor de desarrollo: es el mismo CSS y el mismo bundle que se despliega, y
 * los problemas de maquetado aparecen ahí. jsdom, que es lo que usan los tests
 * de componente, no tiene motor de maquetado y no mide nada (ADR-0013).
 *
 * La dirección va como 127.0.0.1 y no como localhost: en Windows este resuelve
 * primero a IPv6 y la conexión se cuelga en lugar de fallar.
 */
const BASE_URL = "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // En CI, un `test.only` olvidado dejaría pasar todo lo demás sin correr.
  forbidOnly: Boolean(process.env.CI),
  // Un reintento solo en CI: distingue un fallo real de uno de infraestructura,
  // sin tapar un test genuinamente inestable, que queda marcado como inestable.
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run build && npm run preview -- --port 4173 --strictPort --host 127.0.0.1",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
