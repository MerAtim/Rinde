import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type Quote = components["schemas"]["QuoteResponse"];
export type RateType = components["schemas"]["RateType"];
export type Conversion = components["schemas"]["ConversionResponse"];
type Currency = components["schemas"]["Currency"];

/** Códigos estables que devuelve la API de cotizaciones. */
const SERVER_CODES = [
  "RATE_NOT_FOUND",
  "CONVERSION_NOT_SUPPORTED",
  "CONVERSION_SAME_CURRENCY",
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

export interface ConversionInput {
  rateType: RateType;
  /** String decimal, tal como lo devolvió el servidor: no pasa por un número. */
  amount: string;
  currency: Currency;
  target: Currency;
}

/** Hoy, con la compra o la venta según el caso (ADR-0017). El cálculo es del servidor. */
export async function fetchConversion(
  input: ConversionInput,
  signal: AbortSignal,
): Promise<Conversion> {
  const query = new URLSearchParams({
    amount: input.amount,
    currency: input.currency,
    target: input.target,
  });
  const response = await api.get(
    `/api/rates/${encodeURIComponent(input.rateType)}/conversion?${query.toString()}`,
    signal,
  );
  return (await response.json()) as Conversion;
}
