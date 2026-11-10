import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";
import type { RateType } from "../rates/api";

export type Preferences = components["schemas"]["PreferencesResponse"];
export type ReferenceCurrency = Preferences["reference_currency"];

// El orden es el de la pantalla: el más usado para valuar ahorros, primero.
export const RATE_TYPES = [
  "mep",
  "official",
  "blue",
  "ccl",
  "crypto",
  "card",
] as const satisfies readonly RateType[];
export const REFERENCE_CURRENCIES = ["ARS", "USD"] as const satisfies readonly ReferenceCurrency[];

/** Códigos estables que devuelve la API de preferencias. */
const SERVER_CODES = [
  "PREFERENCES_CURRENCY_NOT_ALLOWED",
  "NOT_AUTHENTICATED",
  "CSRF_REJECTED",
] as const;

export type PreferencesErrorCode = (typeof SERVER_CODES)[number] | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isPreferencesApiError = api.isError;

export async function fetchPreferences(signal: AbortSignal): Promise<Preferences> {
  const response = await api.get("/api/preferences", signal);
  return (await response.json()) as Preferences;
}

export async function updatePreferences(input: Preferences): Promise<Preferences> {
  const response = await api.put("/api/preferences", input);
  return (await response.json()) as Preferences;
}
