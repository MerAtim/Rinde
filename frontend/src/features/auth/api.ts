import { ApiRequestError, createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type Session = components["schemas"]["MeResponse"];
export type RegisterResponse = components["schemas"]["RegisterResponse"];
export type RecoverResponse = components["schemas"]["RecoverResponse"];

/** Códigos estables que devuelve la API (ADR-0007). */
const SERVER_CODES = [
  "USERNAME_INVALID",
  "USERNAME_RESERVED",
  "USERNAME_TAKEN",
  "PASSWORD_TOO_SHORT",
  "PASSWORD_TOO_LONG",
  "PASSWORD_CONTAINS_USERNAME",
  "PASSWORD_TOO_SIMPLE",
  "PASSWORD_COMPROMISED",
  "INVALID_CREDENTIALS",
  "RECOVERY_CODE_INVALID",
  "TOO_MANY_ATTEMPTS",
  "NOT_AUTHENTICATED",
  "CSRF_REJECTED",
] as const;

/** Los del servidor, más los que detecta el propio formulario o la red. */
export type AuthErrorCode =
  | (typeof SERVER_CODES)[number]
  | "USERNAME_REQUIRED"
  | "PASSWORD_REQUIRED"
  | "RECOVERY_CODE_REQUIRED"
  | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isAuthApiError = api.isError;

/** La sesión actual, o null si no hay ninguna abierta. */
export async function fetchSession(signal: AbortSignal): Promise<Session | null> {
  try {
    const response = await api.get("/api/auth/me", signal);
    return (await response.json()) as Session;
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export async function register(username: string, password: string): Promise<RegisterResponse> {
  const response = await api.post("/api/auth/register", { username, password });
  return (await response.json()) as RegisterResponse;
}

export async function login(username: string, password: string): Promise<void> {
  await api.post("/api/auth/login", { username, password });
}

export async function logout(): Promise<void> {
  await api.post("/api/auth/logout");
}

export async function recover(
  username: string,
  recoveryCode: string,
  newPassword: string,
): Promise<RecoverResponse> {
  const response = await api.post("/api/auth/recover", {
    username,
    recovery_code: recoveryCode,
    new_password: newPassword,
  });
  return (await response.json()) as RecoverResponse;
}
