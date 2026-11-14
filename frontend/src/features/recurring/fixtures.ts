import { anAccount } from "../accounts/fixtures";
import { EXPENSE_CATEGORY } from "../transactions/fixtures";
import type { RecurringRule } from "./api";

/** El alquiler, todos los meses: ya se registró dos veces y la próxima es en octubre. */
export function aRule(overrides: Partial<RecurringRule> = {}): RecurringRule {
  return {
    id: "5c6d7e8f-9a0b-4c1d-8e2f-3a4b5c6d7e8f",
    account_id: anAccount().id,
    kind: "expense",
    amount: "450000.00",
    currency: "ARS",
    category_id: EXPENSE_CATEGORY.id,
    frequency: "monthly",
    starts_on: "2026-08-10",
    description: "Alquiler",
    created_at: "2026-09-18T13:00:00Z",
    cancelled_at: null,
    generated: 2,
    next_on: "2026-10-10",
    ...overrides,
  };
}
