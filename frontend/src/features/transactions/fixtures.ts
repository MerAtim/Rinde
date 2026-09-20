import type { Transfer } from "../transfers/api";
import type { Balance, Category, HistoryPage, Transaction, TransactionPage } from "./api";

/** Gasto de ejemplo: supermercado en pesos, de hoy. */
export function aTransaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: "3f1a2b3c-4d5e-4f60-8a1b-2c3d4e5f6a7b",
    account_id: "0b6d7c1e-2f4a-4e8b-9c3d-5a6b7c8d9e0f",
    kind: "expense",
    amount: "15300.50",
    currency: "ARS",
    category_id: "11111111-1111-4111-8111-111111111111",
    occurred_on: "2026-09-18",
    description: "Coto",
    created_at: "2026-09-18T13:00:00Z",
    updated_at: "2026-09-18T13:00:00Z",
    deleted_at: null,
    ...overrides,
  };
}

export function aPage(items: Transaction[], nextCursor: string | null = null): TransactionPage {
  return { items, next_cursor: nextCursor };
}

export const EXPENSE_CATEGORY: Category = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Supermercado",
  kind: "expense",
  slug: "supermercado",
};

export const INCOME_CATEGORY: Category = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Sueldo",
  kind: "income",
  slug: "sueldo",
};

export function aBalance(overrides: Partial<Balance> = {}): Balance {
  return {
    account_id: "0b6d7c1e-2f4a-4e8b-9c3d-5a6b7c8d9e0f",
    amount: "84699.50",
    currency: "ARS",
    ...overrides,
  };
}

/**
 * Una página del historial, con movimientos y transferencias mezclados.
 *
 * El tipo se deduce de la forma: solo un movimiento tiene `kind`. Así el test
 * se escribe con las entidades y no con la envoltura de la API.
 */
export function aHistoryPage(
  items: (Transaction | Transfer)[],
  nextCursor: string | null = null,
): HistoryPage {
  return {
    items: items.map((item) =>
      "kind" in item
        ? { type: "transaction" as const, transaction: item }
        : { type: "transfer" as const, transfer: item },
    ),
    next_cursor: nextCursor,
  };
}
