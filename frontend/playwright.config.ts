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
 *
 * El puerto se cambia con RINDE_E2E_PORT, por si el 4173 lo usa otro proyecto:
 * es el puerto por defecto de `vite preview`.
 */
const PORT = Number(process.env.RINDE_E2E_PORT ?? "4173");
if (!Number.isInteger(PORT) || PORT < 1024 || PORT > 65535) {
  throw new Error(`RINDE_E2E_PORT tiene que ser un puerto entre 1024 y 65535: ${String(PORT)}`);
}
const BASE_URL = `http://127.0.0.1:${String(PORT)}`;

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
    command: `npm run build && npm run preview -- --port ${String(PORT)} --strictPort --host 127.0.0.1`,
    url: BASE_URL,
    // Nunca se reutiliza lo que ya esté escuchando en el puerto. Pasó: había
    // otra aplicación en el 4173, las pruebas corrieron contra ella y fallaron
    // todas contra su página 404. Si hubiera tenido una navegación parecida,
    // habrían pasado sin probar Rinde. Con el puerto ocupado, `--strictPort`
    // hace fallar el arranque con un error claro.
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
