import type { Account } from "./api";

/** Cuenta de ejemplo para tests: una caja de ahorro en pesos, activa. */
export function anAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: "0b6d7c1e-2f4a-4e8b-9c3d-5a6b7c8d9e0f",
    name: "Galicia sueldo",
    kind: "bank",
    currency: "ARS",
    created_at: "2026-09-17T13:00:00Z",
    archived_at: null,
    ...overrides,
  };
}
