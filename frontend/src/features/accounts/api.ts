import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type Account = components["schemas"]["AccountResponse"];
export type AccountKind = components["schemas"]["AccountKind"];
export type Currency = components["schemas"]["Currency"];

// El orden es el de la pantalla: primero lo más cotidiano.
export const ACCOUNT_KINDS = [
  "cash",
  "bank",
  "credit_card",
  "crypto_wallet",
] as const satisfies readonly AccountKind[];
export const CURRENCIES = ["ARS", "USD", "BTC"] as const satisfies readonly Currency[];

/** Igual que el dominio (ADR-0009): Bitcoin solo en billeteras cripto. */
export function isCurrencyAllowed(kind: AccountKind, currency: Currency): boolean {
  return currency !== "BTC" || kind === "crypto_wallet";
}

/** Igual que `AccountName.MAX_LENGTH` en el backend. */
export const ACCOUNT_NAME_MAX_LENGTH = 60;

/** Códigos estables que devuelve la API de cuentas. */
const SERVER_CODES = [
  "ACCOUNT_NAME_INVALID",
  "ACCOUNT_CURRENCY_NOT_ALLOWED",
  "ACCOUNT_NOT_FOUND",
  "ACCOUNT_ARCHIVED",
  "NOT_AUTHENTICATED",
  "CSRF_REJECTED",
] as const;

/** Los del servidor, más los que detecta el propio formulario o la red. */
export type AccountErrorCode =
  (typeof SERVER_CODES)[number] | "ACCOUNT_NAME_REQUIRED" | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isAccountsApiError = api.isError;

export async function fetchAccounts(
  includeArchived: boolean,
  signal: AbortSignal,
): Promise<Account[]> {
  const query = includeArchived ? "?include_archived=true" : "";
  const response = await api.get(`/api/accounts${query}`, signal);
  return (await response.json()) as Account[];
}

export async function fetchAccount(id: string, signal: AbortSignal): Promise<Account> {
  const response = await api.get(`/api/accounts/${encodeURIComponent(id)}`, signal);
  return (await response.json()) as Account;
}

export interface OpenAccountInput {
  name: string;
  kind: AccountKind;
  currency: Currency;
}

export async function openAccount(input: OpenAccountInput): Promise<Account> {
  const response = await api.post("/api/accounts", input);
  return (await response.json()) as Account;
}

export async function renameAccount(id: string, name: string): Promise<Account> {
  const response = await api.patch(`/api/accounts/${encodeURIComponent(id)}`, { name });
  return (await response.json()) as Account;
}

export async function archiveAccount(id: string): Promise<Account> {
  const response = await api.post(`/api/accounts/${encodeURIComponent(id)}/archive`);
  return (await response.json()) as Account;
}
