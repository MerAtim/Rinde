import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type Quote = components["schemas"]["QuoteResponse"];
export type RateType = components["schemas"]["RateType"];

/** Códigos estables que devuelve la API de cotizaciones. */
const SERVER_CODES = [
  "RATE_NOT_FOUND",
  "RATES_UNAVAILABLE",
  "RATE_DATE_IN_FUTURE",
  "NOT_AUTHENTICATED",
] as const;

export type RatesErrorCode = (typeof SERVER_CODES)[number] | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isRatesApiError = api.isError;

/** Las cotizaciones de hoy. Los tipos que ninguna fuente tiene no vienen: no se inventan. */
export async function fetchTodayRates(signal: AbortSignal): Promise<Quote[]> {
  const response = await api.get("/api/rates", signal);
  return (await response.json()) as Quote[];
}
