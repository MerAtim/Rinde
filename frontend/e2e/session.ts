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
  // Una cuenta en dólares con un saldo largo: su equivalente en pesos es la
  // línea más ancha de la lista.
  await page.route("**/api/accounts*", (route) =>
    route.fulfill(
      json([
        {
          id: "5c4b3a29-1807-4f6e-9d5c-4b3a29180706",
          name: "Caja de ahorro en dólares",
          kind: "bank",
          currency: "USD",
          created_at: "2026-09-17T13:00:00Z",
          archived_at: null,
        },
      ]),
    ),
  );
  await page.route("**/api/transactions/balances", (route) =>
    route.fulfill(
      json([
        {
          account_id: "5c4b3a29-1807-4f6e-9d5c-4b3a29180706",
          amount: "125000.00",
          currency: "USD",
        },
      ]),
    ),
  );
  // Un resumen con montos largos y una categoría de nombre largo: lo más ancho
  // que puede tener el inicio.
  await page.route("**/api/dashboard*", (route) => route.fulfill(json(DASHBOARD)));
  await page.route("**/api/preferences", (route) =>
    route.fulfill(json({ reference_currency: "ARS", rate_type: "crypto" })),
  );
  await page.route("**/api/transactions*", (route) =>
    route.fulfill(json({ items: [], next_cursor: null })),
  );
  await page.route("**/api/categories", (route) => route.fulfill(json([])));
  // Los seis dólares, con montos de cuatro cifras: el peor caso de ancho de la tabla.
  await page.route("**/api/rates/*/conversion*", (route) =>
    route.fulfill(
      json({
        original: { amount: "125000.00", currency: "USD" },
        converted: { amount: "255125000.00", currency: "ARS" },
        rate: "2041.00000000",
        quote: {
          rate_type: "crypto",
          base: "USD",
          counter: "ARS",
          day: "2026-11-10",
          buy: "1976.00000000",
          sell: "2041.00000000",
          source: "dolarapi",
          updated_at: "2026-11-10T14:54:00Z",
        },
      }),
    ),
  );
  await page.route("**/api/rates", (route) =>
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

const ars = (amount: string) => ({ amount, currency: "ARS" });

export const DASHBOARD = {
  period: { first: "2026-06", last: "2026-11", since: "2026-06-01", until: "2026-11-10" },
  reference: { currency: "ARS", rate_type: "crypto" },
  spending: [
    {
      category: {
        id: "0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9",
        name: "Expensas del departamento y servicios",
        slug: null,
      },
      total: ars("12450300.50"),
    },
    {
      category: { id: "1c2d3e4f-5061-4728-93a4-b5c6d7e8f90a", name: "Transporte", slug: null },
      total: ars("420000.00"),
    },
  ],
  monthly: ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"].map(
    (month, index) => ({
      month,
      income: ars("98500000.00"),
      expense: ars(index % 2 === 0 ? "61200000.00" : "99950000.00"),
      net: ars(index % 2 === 0 ? "37300000.00" : "-1450000.00"),
    }),
  ),
  net_worth: ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"].map(
    (month, index) => ({
      month,
      on: `${month}-28`,
      total: index === 3 ? null : ars(`${String(250000000 + index * 9000000)}.75`),
    }),
  ),
  unconverted: [
    {
      currency: "BTC",
      income: { amount: "0.00000000", currency: "BTC" },
      expense: { amount: "0.00000000", currency: "BTC" },
      balance: { amount: "12.34567890", currency: "BTC" },
    },
  ],
};
