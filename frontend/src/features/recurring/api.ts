import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";
import type { TransactionKind } from "../transactions/api";

export type RecurringRule = components["schemas"]["RecurringRuleResponse"];
export type Frequency = components["schemas"]["Frequency"];

export const FREQUENCIES = ["weekly", "monthly", "yearly"] as const satisfies readonly Frequency[];

/** Códigos estables que devuelve la API de movimientos recurrentes. */
const SERVER_CODES = [
  "RECURRING_RULE_NOT_FOUND",
  "RECURRING_RULE_CANCELLED",
  "RECURRING_START_OUT_OF_RANGE",
  "TRANSACTION_AMOUNT_NOT_POSITIVE",
  "TRANSACTION_CURRENCY_MISMATCH",
  "TRANSACTION_DESCRIPTION_INVALID",
  "CATEGORY_NOT_FOUND",
  "CATEGORY_KIND_MISMATCH",
  "ACCOUNT_NOT_FOUND",
  "ACCOUNT_ARCHIVED",
  "IDEMPOTENCY_KEY_REUSED",
  "AMOUNT_INVALID",
  "AMOUNT_TOO_PRECISE",
  "NOT_AUTHENTICATED",
  "CSRF_REJECTED",
] as const;

/** Los del servidor, más los que detecta el propio formulario o la red. */
export type RecurringErrorCode =
  | (typeof SERVER_CODES)[number]
  | "AMOUNT_REQUIRED"
  | "CATEGORY_REQUIRED"
  | "DATE_REQUIRED"
  | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isRecurringApiError = api.isError;

export interface RuleInput {
  account_id: string;
  kind: TransactionKind;
  /** String decimal: en el frontend no se hace aritmética de dinero (ADR-0002). */
  amount: string;
  category_id: string;
  frequency: Frequency;
  starts_on: string;
  description: string | null;
}

export interface RuleChange {
  amount: string;
  description: string | null;
}

export async function fetchRules(signal: AbortSignal): Promise<RecurringRule[]> {
  const response = await api.get("/api/recurring", signal);
  return (await response.json()) as RecurringRule[];
}

export async function createRule(input: RuleInput, idempotencyKey: string): Promise<RecurringRule> {
  // Con la clave, un reintento por red caída no duplica la regla.
  const response = await api.post("/api/recurring", input, {
    "Idempotency-Key": idempotencyKey,
  });
  return (await response.json()) as RecurringRule;
}

export async function changeRule(id: string, change: RuleChange): Promise<RecurringRule> {
  const response = await api.patch(`/api/recurring/${encodeURIComponent(id)}`, change);
  return (await response.json()) as RecurringRule;
}

export async function cancelRule(id: string): Promise<RecurringRule> {
  const response = await api.post(`/api/recurring/${encodeURIComponent(id)}/cancel`);
  return (await response.json()) as RecurringRule;
}

/** Lo vencido de todas las reglas. Repetirlo no duplica nada (ADR-0027). */
export async function generateDue(): Promise<{ created: number }> {
  const response = await api.post("/api/recurring/due");
  return (await response.json()) as { created: number };
}
