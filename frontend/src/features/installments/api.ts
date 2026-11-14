import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type InstallmentPlan = components["schemas"]["InstallmentPlanResponse"];
export type ScheduledInstallment = InstallmentPlan["installments"][number];

/** Los mismos topes que `InstallmentPlan` en el backend (ADR-0026). */
export const MIN_COUNT = 2;
export const MAX_COUNT = 48;

/** Códigos estables que devuelve la API de cuotas. */
const SERVER_CODES = [
  "INSTALLMENT_PLAN_NOT_FOUND",
  "INSTALLMENT_COUNT_INVALID",
  "INSTALLMENT_AMOUNT_TOO_SMALL",
  "TRANSACTION_AMOUNT_NOT_POSITIVE",
  "TRANSACTION_CURRENCY_MISMATCH",
  "TRANSACTION_DATE_IN_FUTURE",
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
export type InstallmentErrorCode =
  | (typeof SERVER_CODES)[number]
  | "AMOUNT_REQUIRED"
  | "CATEGORY_REQUIRED"
  | "DATE_REQUIRED"
  | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isInstallmentsApiError = api.isError;

export interface PlanInput {
  account_id: string;
  category_id: string;
  /** String decimal: en el frontend no se hace aritmética de dinero (ADR-0002). */
  total: string;
  count: number;
  first_on: string;
  description: string | null;
}

export async function fetchPlans(signal: AbortSignal): Promise<InstallmentPlan[]> {
  const response = await api.get("/api/installments", signal);
  return (await response.json()) as InstallmentPlan[];
}

export async function createPlan(
  input: PlanInput,
  idempotencyKey: string,
): Promise<InstallmentPlan> {
  // Con la clave, un reintento por red caída no duplica la compra.
  const response = await api.post("/api/installments", input, {
    "Idempotency-Key": idempotencyKey,
  });
  return (await response.json()) as InstallmentPlan;
}

export async function cancelPlan(id: string): Promise<InstallmentPlan> {
  const response = await api.post(`/api/installments/${encodeURIComponent(id)}/cancel`);
  return (await response.json()) as InstallmentPlan;
}

/** Las cuotas vencidas de todos los planes. Repetirlo no duplica nada (ADR-0026). */
export async function generateDue(): Promise<{ created: number }> {
  const response = await api.post("/api/installments/due");
  return (await response.json()) as { created: number };
}
