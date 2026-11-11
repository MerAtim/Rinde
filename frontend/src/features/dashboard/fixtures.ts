import type { Dashboard } from "./api";

const ars = (amount: string) => ({ amount, currency: "ARS" as const });

/** Tres meses en pesos, con un cierre sin cotización y un saldo en Bitcoin que no se convierte. */
export function aDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    period: { first: "2026-09", last: "2026-11", since: "2026-09-01", until: "2026-11-11" },
    reference: { currency: "ARS", rate_type: "mep" },
    spending: [
      {
        category: { id: "0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9", name: "Supermercado", slug: null },
        total: ars("150300.50"),
      },
      {
        category: { id: "1c2d3e4f-5061-4728-93a4-b5c6d7e8f90a", name: "Transporte", slug: null },
        total: ars("42000.00"),
      },
    ],
    monthly: [
      {
        month: "2026-09",
        income: ars("900000.00"),
        expense: ars("620000.00"),
        net: ars("280000.00"),
      },
      {
        month: "2026-10",
        income: ars("900000.00"),
        expense: ars("950000.00"),
        net: ars("-50000.00"),
      },
      { month: "2026-11", income: ars("0.00"), expense: ars("0.00"), net: ars("0.00") },
    ],
    net_worth: [
      { month: "2026-09", on: "2026-09-30", total: ars("3100000.00") },
      { month: "2026-10", on: "2026-10-31", total: null },
      { month: "2026-11", on: "2026-11-11", total: ars("3550000.75") },
    ],
    unconverted: [
      {
        currency: "BTC",
        income: { amount: "0.00000000", currency: "BTC" },
        expense: { amount: "0.00000000", currency: "BTC" },
        balance: { amount: "0.01250000", currency: "BTC" },
      },
    ],
    ...overrides,
  };
}
