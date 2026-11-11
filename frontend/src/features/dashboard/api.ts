import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type Dashboard = components["schemas"]["DashboardResponse"];
export type MonthFlow = components["schemas"]["MonthFlowResponse"];
export type NetWorthPoint = components["schemas"]["NetWorthPointResponse"];
export type CategorySpending = components["schemas"]["CategorySpendingResponse"];
export type Unconverted = components["schemas"]["UnconvertedResponse"];

/** Códigos estables que devuelve la API del dashboard. */
const SERVER_CODES = ["DASHBOARD_PERIOD_INVALID", "NOT_AUTHENTICATED"] as const;

export type DashboardErrorCode = (typeof SERVER_CODES)[number] | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isDashboardApiError = api.isError;

export interface DashboardQuery {
  /** Primer mes, AAAA-MM. Sin él, el servidor usa los últimos seis meses. */
  from?: string;
  accountId?: string;
}

export function dashboardPath(query: DashboardQuery): string {
  const params = new URLSearchParams();
  if (query.from) params.set("from", query.from);
  if (query.accountId) params.set("account", query.accountId);
  const search = params.toString();
  return search ? `/api/dashboard?${search}` : "/api/dashboard";
}

export async function fetchDashboard(
  query: DashboardQuery,
  signal: AbortSignal,
): Promise<Dashboard> {
  const response = await api.get(dashboardPath(query), signal);
  return (await response.json()) as Dashboard;
}
