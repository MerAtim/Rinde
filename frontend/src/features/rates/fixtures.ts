import type { Quote } from "./api";

/** Cotización de ejemplo para tests: el MEP del 10 de noviembre de 2026, de DolarAPI. */
export function aQuote(overrides: Partial<Quote> = {}): Quote {
  return {
    rate_type: "mep",
    base: "USD",
    counter: "ARS",
    day: "2026-11-10",
    buy: "1560.20000000",
    sell: "1587.90000000",
    source: "dolarapi",
    updated_at: "2026-11-10T14:54:00Z",
    ...overrides,
  };
}
