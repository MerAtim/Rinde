import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type BudgetMonth = components["schemas"]["BudgetsResponse"];
export type Budget = components["schemas"]["BudgetResponse"];
export type BudgetStatus = Budget["status"];
export type BudgetInput = components["schemas"]["BudgetRequest"];

/** Las que tienen cotización entre sí: Bitcoin no puede ser la moneda de un tope. */
export const BUDGET_CURRENCIES = ["ARS", "USD"] as const;
export type BudgetCurrency = (typeof BUDGET_CURRENCIES)[number];

/** Códigos estables que devuelve la API de presupuestos. */
const SERVER_CODES = [
  "BUDGET_NOT_FOUND",
  "BUDGET_CATEGORY_NOT_FOUND",
  "BUDGET_CATEGORY_NOT_EXPENSE",
  "BUDGET_AMOUNT_INVALID",
  "BUDGET_CURRENCY_NOT_ALLOWED",
  "BUDGET_MONTH_INVALID",
  "AMOUNT_TOO_PRECISE",
  "NOT_AUTHENTICATED",
  "CSRF_REJECTED",
] as const;

export type BudgetServerCode = (typeof SERVER_CODES)[number];
export type BudgetErrorCode = BudgetServerCode | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isBudgetsApiError = api.isError;

/** Sin mes, el servidor responde por el mes en curso: el reloj que vale es el suyo. */
export function budgetsPath(month: string | null): string {
  return month ? `/api/budgets?${new URLSearchParams({ month }).toString()}` : "/api/budgets";
}

export async function fetchBudgets(
  month: string | null,
  signal: AbortSignal,
): Promise<BudgetMonth> {
  const response = await api.get(budgetsPath(month), signal);
  return (await response.json()) as BudgetMonth;
}

export async function setBudget(categoryId: string, input: BudgetInput): Promise<void> {
  await api.put(`/api/budgets/${encodeURIComponent(categoryId)}`, input);
}

export async function removeBudget(categoryId: string): Promise<void> {
  await api.delete(`/api/budgets/${encodeURIComponent(categoryId)}`);
}
