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
  // Montos largos, un tope pasado y una categoría propia de nombre largo: lo más
  // ancho que puede tener una fila de presupuestos.
  await page.route("**/api/budgets*", (route) => route.fulfill(json(BUDGETS)));
  // Más de 9 sin leer: el badge más ancho que puede tener la campana.
  await page.route("**/api/alerts", (route) => route.fulfill(json(ALERTS)));
  // Descripciones y montos largos: lo más ancho que puede tener una vista previa.
  await page.route("**/api/imports/*", (route) => route.fulfill(json(BATCH)));
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

export const BUDGETS = {
  month: "2026-11",
  rate_type: "crypto",
  budgets: [
    {
      category: {
        id: "6d5c4b3a-2918-4f07-8e6d-5c4b3a291807",
        name: "Mantenimiento del departamento",
        slug: null,
      },
      since: "2026-09",
      limit: { amount: "12345678.90", currency: "ARS" },
      spent: { amount: "10987654.32", currency: "ARS" },
      remaining: { amount: "1358024.58", currency: "ARS" },
      ratio: "0.8900",
      status: "warning",
      unconverted: [{ amount: "0.00150000", currency: "BTC" }],
    },
    {
      category: { id: "7e6d5c4b-3a29-4f18-8f7e-6d5c4b3a2918", name: "Alquiler", slug: "alquiler" },
      since: "2026-11",
      limit: { amount: "1500.00", currency: "USD" },
      spent: { amount: "1987654.32", currency: "USD" },
      remaining: { amount: "-1986154.32", currency: "USD" },
      ratio: "1325.1029",
      status: "over",
      unconverted: [],
    },
  ],
};

export const ALERTS = {
  unread: 128,
  alerts: [
    {
      id: "8f7e6d5c-4b3a-4291-8a7e-6d5c4b3a2919",
      category: {
        id: "6d5c4b3a-2918-4f07-8e6d-5c4b3a291807",
        name: "Mantenimiento del departamento",
        slug: null,
      },
      month: "2026-11",
      threshold: "warning",
      limit: { amount: "12345678.90", currency: "ARS" },
      spent: { amount: "10987654.32", currency: "ARS" },
      raised_at: "2026-11-10T15:00:00Z",
      read: false,
    },
    {
      id: "9a8f7e6d-5c4b-4a32-9b8f-7e6d5c4b3a2a",
      category: { id: "7e6d5c4b-3a29-4f18-8f7e-6d5c4b3a2918", name: "Alquiler", slug: "alquiler" },
      month: "2026-10",
      threshold: "over",
      limit: { amount: "1500.00", currency: "USD" },
      spent: { amount: "1987654.32", currency: "USD" },
      raised_at: "2026-10-28T23:59:00Z",
      read: true,
    },
  ],
};

export const BATCH = {
  id: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  account_id: "6d5c4b3a-2918-4f07-8e6d-5c4b3a291807",
  file_name: "resumen-de-movimientos-caja-de-ahorro-en-pesos-octubre-2026.csv",
  created_at: "2026-11-10T15:00:00Z",
  expires_at: "2026-11-11T15:00:00Z",
  confirmed: false,
  lines: [
    {
      number: 2,
      occurred_on: "2026-11-03",
      description:
        "TRANSFERENCIA A TERCEROS REF 0000000000000000000000 ALQUILER DEPARTAMENTO CENTRO",
      amount: { amount: "-12345678.90", currency: "ARS" },
      status: "new",
      category_id: null,
      rule: null,
    },
    {
      number: 3,
      occurred_on: "2026-11-05",
      description: "INTERESES CAJA DE AHORRO",
      amount: { amount: "12.34", currency: "ARS" },
      status: "possible_duplicate",
      category_id: null,
      rule: null,
    },
    {
      number: 4,
      occurred_on: "2026-11-06",
      description: "DEBITO AUTOMATICO SEGURO DE VIDA",
      amount: { amount: "-4321.09", currency: "ARS" },
      status: "duplicate",
      category_id: null,
      rule: null,
    },
  ],
  errors: [{ line: 5, problem: "LINE_AMOUNT_TOO_PRECISE" }],
};
