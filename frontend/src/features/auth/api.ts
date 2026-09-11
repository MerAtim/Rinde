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
  | "NETWORK_ERROR"
  | "UNKNOWN_ERROR";

export class AuthApiError extends Error {
  readonly code: AuthErrorCode;
  readonly status: number;

  constructor(code: AuthErrorCode, status: number) {
    super(code);
    this.name = "AuthApiError";
    this.code = code;
    this.status = status;
  }
}

// Sin este encabezado la API rechaza las acciones que cambian estado (defensa CSRF).
const CSRF_HEADER = { "X-Requested-With": "rinde" };

function isServerCode(value: unknown): value is (typeof SERVER_CODES)[number] {
  return SERVER_CODES.some((code) => code === value);
}

async function codeFrom(response: Response): Promise<AuthErrorCode> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "code" in body && isServerCode(body.code)) {
      return body.code;
    }
  } catch {
    // El cuerpo no es JSON: se informa como error desconocido.
  }
  return "UNKNOWN_ERROR";
}

async function send(path: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...init });
  } catch {
    throw new AuthApiError("NETWORK_ERROR", 0);
  }
  if (!response.ok) {
    throw new AuthApiError(await codeFrom(response), response.status);
  }
  return response;
}

function post(path: string, body?: object): Promise<Response> {
  return send(path, {
    method: "POST",
    headers: body
      ? { ...CSRF_HEADER, Accept: "application/json", "Content-Type": "application/json" }
      : { ...CSRF_HEADER, Accept: "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
}

/** La sesión actual, o null si no hay ninguna abierta. */
export async function fetchSession(signal: AbortSignal): Promise<Session | null> {
  try {
    const response = await send("/api/auth/me", {
      headers: { Accept: "application/json" },
      signal,
    });
    return (await response.json()) as Session;
  } catch (error) {
    if (error instanceof AuthApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export async function register(username: string, password: string): Promise<RegisterResponse> {
  const response = await post("/api/auth/register", { username, password });
  return (await response.json()) as RegisterResponse;
}

export async function login(username: string, password: string): Promise<void> {
  await post("/api/auth/login", { username, password });
}

export async function logout(): Promise<void> {
  await post("/api/auth/logout");
}

export async function recover(
  username: string,
  recoveryCode: string,
  newPassword: string,
): Promise<RecoverResponse> {
  const response = await post("/api/auth/recover", {
    username,
    recovery_code: recoveryCode,
    new_password: newPassword,
  });
  return (await response.json()) as RecoverResponse;
}
