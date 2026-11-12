import { RENT_CATEGORY } from "../budgets/fixtures";
import { EXPENSE_CATEGORY } from "../transactions/fixtures";
import type { AlertFeed, BudgetAlert } from "./api";

export function anAlert(overrides: Partial<BudgetAlert> = {}): BudgetAlert {
  return {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    category: { id: EXPENSE_CATEGORY.id, name: EXPENSE_CATEGORY.name, slug: EXPENSE_CATEGORY.slug },
    month: "2026-11",
    threshold: "warning",
    limit: { amount: "300000.00", currency: "ARS" },
    spent: { amount: "245000.00", currency: "ARS" },
    raised_at: "2026-11-10T15:00:00Z",
    read: false,
    ...overrides,
  };
}

/** Alquiler pasado este mes, sin leer; Supermercado cerca del tope en octubre, leída. */
export function aFeed(overrides: Partial<AlertFeed> = {}): AlertFeed {
  return {
    unread: 1,
    alerts: [
      anAlert({
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        category: { id: RENT_CATEGORY.id, name: RENT_CATEGORY.name, slug: RENT_CATEGORY.slug },
        threshold: "over",
        limit: { amount: "500.00", currency: "USD" },
        spent: { amount: "512.50", currency: "USD" },
      }),
      anAlert({ month: "2026-10", raised_at: "2026-10-20T13:30:00Z", read: true }),
    ],
    ...overrides,
  };
}
