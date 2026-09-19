import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type Transfer = components["schemas"]["TransferResponse"];
export type TransferPage = components["schemas"]["TransferPageResponse"];
export type TransferInput = components["schemas"]["TransferRequest"];

/** Códigos estables que devuelve la API de transferencias. */
const SERVER_CODES = [
  "TRANSFER_NOT_FOUND",
  "TRANSFER_SAME_ACCOUNT",
  "TRANSFER_AMOUNT_NOT_POSITIVE",
  "TRANSFER_CURRENCY_MISMATCH",
  "TRANSFER_DATE_IN_FUTURE",
  "TRANSFER_DELETED",
  "TRANSACTION_DESCRIPTION_INVALID",
  "ACCOUNT_NOT_FOUND",
  "ACCOUNT_ARCHIVED",
  "IDEMPOTENCY_KEY_REUSED",
  "CURSOR_INVALID",
  "AMOUNT_INVALID",
  "AMOUNT_TOO_PRECISE",
  "NOT_AUTHENTICATED",
  "CSRF_REJECTED",
] as const;

/** Los del servidor, más los que detecta el propio formulario o la red. */
export type TransferErrorCode =
  | (typeof SERVER_CODES)[number]
  | "SENT_REQUIRED"
  | "RECEIVED_REQUIRED"
  | "DATE_REQUIRED"
  | "ACCOUNTS_REQUIRED"
  | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isTransfersApiError = api.isError;

export interface TransferFilters {
  accountId?: string;
  cursor?: string;
  limit?: number;
}

function queryOf(filters: TransferFilters): string {
  const params = new URLSearchParams();
  if (filters.accountId) params.set("account_id", filters.accountId);
  if (filters.cursor) params.set("cursor", filters.cursor);
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function fetchTransfers(
  filters: TransferFilters,
  signal: AbortSignal,
): Promise<TransferPage> {
  const response = await api.get(`/api/transfers${queryOf(filters)}`, signal);
  return (await response.json()) as TransferPage;
}

export async function registerTransfer(
  input: TransferInput,
  idempotencyKey: string,
): Promise<Transfer> {
  // Con la clave, un reintento por red caída no mueve la plata dos veces.
  const response = await api.post("/api/transfers", input, {
    "Idempotency-Key": idempotencyKey,
  });
  return (await response.json()) as Transfer;
}

export async function deleteTransfer(id: string): Promise<Transfer> {
  const response = await api.delete(`/api/transfers/${encodeURIComponent(id)}`);
  return (await response.json()) as Transfer;
}

export async function restoreTransfer(id: string): Promise<Transfer> {
  const response = await api.post(`/api/transfers/${encodeURIComponent(id)}/restore`);
  return (await response.json()) as Transfer;
}
