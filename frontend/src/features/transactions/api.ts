import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type Transaction = components["schemas"]["TransactionResponse"];
export type TransactionPage = components["schemas"]["TransactionPageResponse"];
export type TransactionKind = components["schemas"]["TransactionKind"];
export type Category = components["schemas"]["CategoryResponse"];
export type Balance = components["schemas"]["BalanceResponse"];
export type HistoryPage = components["schemas"]["HistoryPageResponse"];
/** Un movimiento o una transferencia: el campo `type` dice cuál (ADR-0014). */
export type HistoryEntry = HistoryPage["items"][number];

export const TRANSACTION_KINDS = [
  "expense",
  "income",
] as const satisfies readonly TransactionKind[];

/** Igual que `Description.MAX_LENGTH` y `CategoryName.MAX_LENGTH` en el backend. */
export const DESCRIPTION_MAX_LENGTH = 120;
export const CATEGORY_NAME_MAX_LENGTH = 40;

/** Códigos estables que devuelve la API de movimientos. */
const SERVER_CODES = [
  "TRANSACTION_NOT_FOUND",
  "TRANSACTION_AMOUNT_NOT_POSITIVE",
  "TRANSACTION_CURRENCY_MISMATCH",
  "TRANSACTION_DATE_IN_FUTURE",
  "TRANSACTION_DESCRIPTION_INVALID",
  "TRANSACTION_DELETED",
  "CATEGORY_NOT_FOUND",
  "CATEGORY_NAME_INVALID",
  "CATEGORY_KIND_MISMATCH",
  "CATEGORY_IN_USE",
  "CATEGORY_NAME_TAKEN",
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
export type TransactionErrorCode =
  | (typeof SERVER_CODES)[number]
  | "AMOUNT_REQUIRED"
  | "CATEGORY_REQUIRED"
  | "DATE_REQUIRED"
  | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isTransactionsApiError = api.isError;

export interface TransactionFilters {
  accountId?: string;
  categoryId?: string;
  /** Busca en la descripción, sin distinguir tildes ni mayúsculas. */
  text?: string;
  since?: string;
  until?: string;
  cursor?: string;
  limit?: number;
}

function queryOf(filters: TransactionFilters): string {
  const params = new URLSearchParams();
  if (filters.accountId) params.set("account_id", filters.accountId);
  if (filters.categoryId) params.set("category_id", filters.categoryId);
  if (filters.text) params.set("q", filters.text);
  if (filters.since) params.set("since", filters.since);
  if (filters.until) params.set("until", filters.until);
  if (filters.cursor) params.set("cursor", filters.cursor);
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function fetchTransactions(
  filters: TransactionFilters,
  signal: AbortSignal,
): Promise<TransactionPage> {
  const response = await api.get(`/api/transactions${queryOf(filters)}`, signal);
  return (await response.json()) as TransactionPage;
}

export async function fetchTransaction(id: string, signal: AbortSignal): Promise<Transaction> {
  const response = await api.get(`/api/transactions/${encodeURIComponent(id)}`, signal);
  return (await response.json()) as Transaction;
}

export async function fetchHistory(
  filters: TransactionFilters,
  signal: AbortSignal,
): Promise<HistoryPage> {
  const response = await api.get(`/api/history${queryOf(filters)}`, signal);
  return (await response.json()) as HistoryPage;
}

export async function fetchBalances(signal: AbortSignal): Promise<Balance[]> {
  const response = await api.get("/api/transactions/balances", signal);
  return (await response.json()) as Balance[];
}

export async function fetchCategories(signal: AbortSignal): Promise<Category[]> {
  const response = await api.get("/api/categories", signal);
  return (await response.json()) as Category[];
}

export interface TransactionInput {
  account_id: string;
  kind: TransactionKind;
  /** String decimal: en el frontend no se hace aritmética de dinero (ADR-0002). */
  amount: string;
  category_id: string;
  occurred_on: string;
  description: string | null;
}

export async function registerTransaction(
  input: TransactionInput,
  idempotencyKey: string,
): Promise<Transaction> {
  // Con la clave, un reintento por red caída no duplica el gasto.
  const response = await api.post("/api/transactions", input, {
    "Idempotency-Key": idempotencyKey,
  });
  return (await response.json()) as Transaction;
}

export async function editTransaction(
  id: string,
  input: Omit<TransactionInput, "account_id">,
): Promise<Transaction> {
  const response = await api.patch(`/api/transactions/${encodeURIComponent(id)}`, input);
  return (await response.json()) as Transaction;
}

export async function deleteTransaction(id: string): Promise<Transaction> {
  const response = await api.delete(`/api/transactions/${encodeURIComponent(id)}`);
  return (await response.json()) as Transaction;
}

export async function restoreTransaction(id: string): Promise<Transaction> {
  const response = await api.post(`/api/transactions/${encodeURIComponent(id)}/restore`);
  return (await response.json()) as Transaction;
}
