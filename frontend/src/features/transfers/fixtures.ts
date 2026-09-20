import type { Transfer } from "./api";

/** Transferencia de ejemplo: 50.000 pesos de una cuenta a otra, del 18. */
export function aTransfer(overrides: Partial<Transfer> = {}): Transfer {
  return {
    id: "5c4b3a29-1d0e-4f8a-9b7c-6d5e4f3a2b1c",
    from_account_id: "0b6d7c1e-2f4a-4e8b-9c3d-5a6b7c8d9e0f",
    sent: "50000.00",
    currency_out: "ARS",
    to_account_id: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    received: "50000.00",
    currency_in: "ARS",
    occurred_on: "2026-09-18",
    description: null,
    created_at: "2026-09-18T13:00:00Z",
    updated_at: "2026-09-18T13:00:00Z",
    deleted_at: null,
    ...overrides,
  };
}
