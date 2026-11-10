import type { Page } from "@playwright/test";

/**
 * Responde la API con datos fijos, para probar el maquetado sin backend.
 *
 * Los flujos que necesitan un servidor de verdad van aparte, contra el entorno
 * completo; acá lo que se mide es cómo queda la pantalla, y para eso los datos
 * tienen que ser siempre los mismos o el test se vuelve inestable.
 */
export async function mockSession(page: Page): Promise<void> {
  const json = (body: unknown) => ({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });

  await page.route("**/api/auth/me", (route) => route.fulfill(json({ username: "mechi" })));
  await page.route("**/api/health/ready", (route) =>
    route.fulfill(json({ status: "ok", database: "ok" })),
  );
  await page.route("**/api/accounts*", (route) => route.fulfill(json([])));
  await page.route("**/api/transactions/balances", (route) => route.fulfill(json([])));
  await page.route("**/api/transactions*", (route) =>
    route.fulfill(json({ items: [], next_cursor: null })),
  );
  await page.route("**/api/categories", (route) => route.fulfill(json([])));
  // Los seis dólares, con montos de cuatro cifras: el peor caso de ancho de la tabla.
  await page.route("**/api/rates*", (route) =>
    route.fulfill(
      json(
        (["official", "mep", "ccl", "blue", "card", "crypto"] as const).map((rate_type) => ({
          rate_type,
          base: "USD",
          counter: "ARS",
          day: "2026-11-10",
          buy: "1976.00000000",
          sell: "2041.00000000",
          source: "dolarapi",
          updated_at: "2026-11-05T18:55:00Z",
        })),
      ),
    ),
  );
}
