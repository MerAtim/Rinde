import { anAccount } from "../accounts/fixtures";
import { EXPENSE_CATEGORY, INCOME_CATEGORY } from "../transactions/fixtures";
import type { BatchLine, ImportBatch } from "./api";

export const BATCH_ID = "5e6f7a8b-9c0d-4e1f-8a2b-3c4d5e6f7a8b";

export function aLine(overrides: Partial<BatchLine> = {}): BatchLine {
  return {
    number: 2,
    occurred_on: "2026-11-03",
    description: "COTO SUC 123",
    amount: { amount: "-1500.50", currency: "ARS" },
    status: "new",
    category_id: EXPENSE_CATEGORY.id,
    rule: null,
    ...overrides,
  };
}

/** Un gasto nuevo, un sueldo nuevo, uno ya importado, un posible duplicado y una línea ilegible. */
export function aBatch(overrides: Partial<ImportBatch> = {}): ImportBatch {
  return {
    id: BATCH_ID,
    account_id: anAccount().id,
    file_name: "octubre.csv",
    created_at: "2026-11-10T15:00:00Z",
    expires_at: "2026-11-11T15:00:00Z",
    confirmed: false,
    lines: [
      aLine(),
      aLine({
        number: 3,
        occurred_on: "2026-11-05",
        description: "HABERES",
        amount: { amount: "250000.00", currency: "ARS" },
        category_id: INCOME_CATEGORY.id,
      }),
      aLine({ number: 4, description: "YA ESTABA", status: "duplicate" }),
      aLine({
        number: 5,
        description: "CAFE",
        amount: { amount: "-900.00", currency: "ARS" },
        status: "possible_duplicate",
      }),
    ],
    errors: [{ line: 6, problem: "LINE_DATE_INVALID" }],
    ...overrides,
  };
}
