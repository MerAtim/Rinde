import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type AlertFeed = components["schemas"]["AlertsResponse"];
export type BudgetAlert = components["schemas"]["AlertResponse"];
export type AlertThreshold = BudgetAlert["threshold"];

/** Códigos estables que devuelve la API de alertas. */
const SERVER_CODES = ["NOT_AUTHENTICATED", "CSRF_REJECTED"] as const;

export type AlertsServerCode = (typeof SERVER_CODES)[number];
export type AlertsErrorCode = AlertsServerCode | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isAlertsApiError = api.isError;

export async function fetchAlerts(signal: AbortSignal): Promise<AlertFeed> {
  const response = await api.get("/api/alerts", signal);
  return (await response.json()) as AlertFeed;
}

/** Las que la persona vio, no "todas": una nueva pudo llegar mientras miraba (ADR-0022). */
export async function markAlertsRead(ids: string[]): Promise<void> {
  await api.post("/api/alerts/read", { ids });
}
