import type { Category } from "../transactions/api";
import { EXPENSE_CATEGORY } from "../transactions/fixtures";
import type { Budget, BudgetMonth } from "./api";

export const RENT_CATEGORY: Category = {
  id: "33333333-3333-4333-8333-333333333333",
  name: "Alquiler",
  kind: "expense",
  slug: "alquiler",
};

export const OWN_CATEGORY: Category = {
  id: "44444444-4444-4444-8444-444444444444",
  name: "Clases de tango",
  kind: "expense",
  slug: null,
};

export function aBudget(overrides: Partial<Budget> = {}): Budget {
  return {
    category: {
      id: EXPENSE_CATEGORY.id,
      name: EXPENSE_CATEGORY.name,
      slug: EXPENSE_CATEGORY.slug,
    },
    since: "2026-09",
    limit: { amount: "300000.00", currency: "ARS" },
    spent: { amount: "245000.00", currency: "ARS" },
    remaining: { amount: "55000.00", currency: "ARS" },
    ratio: "0.8167",
    status: "warning",
    unconverted: [],
    ...overrides,
  };
}

/** Supermercado cerca del tope y Alquiler, en dólares, pasado y con Bitcoin afuera. */
export function aBudgetMonth(overrides: Partial<BudgetMonth> = {}): BudgetMonth {
  return {
    month: "2026-11",
    rate_type: "mep",
    budgets: [
      aBudget(),
      aBudget({
        category: { id: RENT_CATEGORY.id, name: RENT_CATEGORY.name, slug: RENT_CATEGORY.slug },
        since: "2026-11",
        limit: { amount: "500.00", currency: "USD" },
        spent: { amount: "512.50", currency: "USD" },
        remaining: { amount: "-12.50", currency: "USD" },
        ratio: "1.0250",
        status: "over",
        unconverted: [{ amount: "0.00150000", currency: "BTC" }],
      }),
    ],
    ...overrides,
  };
}
