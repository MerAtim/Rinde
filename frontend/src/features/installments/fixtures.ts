import { anAccount } from "../accounts/fixtures";
import { EXPENSE_CATEGORY } from "../transactions/fixtures";
import type { InstallmentPlan } from "./api";

/** Una heladera en 3 cuotas: la primera ya es un movimiento y las otras dos faltan. */
export function aPlan(overrides: Partial<InstallmentPlan> = {}): InstallmentPlan {
  return {
    id: "7a8b9c0d-1e2f-4a3b-8c4d-5e6f7a8b9c0d",
    account_id: anAccount().id,
    category_id: EXPENSE_CATEGORY.id,
    total: "100000.00",
    currency: "ARS",
    count: 3,
    first_on: "2026-09-18",
    description: "Heladera",
    created_at: "2026-09-18T13:00:00Z",
    cancelled_at: null,
    pending: "66666.66",
    installments: [
      {
        number: 1,
        due_on: "2026-09-18",
        amount: "33333.34",
        transaction_id: "3f1a2b3c-4d5e-4f60-8a1b-2c3d4e5f6a7b",
        deleted: false,
      },
      { number: 2, due_on: "2026-10-18", amount: "33333.33", transaction_id: null, deleted: false },
      { number: 3, due_on: "2026-11-18", amount: "33333.33", transaction_id: null, deleted: false },
    ],
    ...overrides,
  };
}
