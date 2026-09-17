import { type AuthErrorCode, isAuthApiError } from "./api";

export type AuthField = "username" | "password" | "recoveryCode";

// Cada error aparece junto al campo que lo causa; el resto, arriba del formulario.
const FIELD_BY_CODE: Partial<Record<AuthErrorCode, AuthField>> = {
  USERNAME_REQUIRED: "username",
  USERNAME_INVALID: "username",
  USERNAME_RESERVED: "username",
  USERNAME_TAKEN: "username",
  PASSWORD_REQUIRED: "password",
  PASSWORD_TOO_SHORT: "password",
  PASSWORD_TOO_LONG: "password",
  PASSWORD_CONTAINS_USERNAME: "password",
  PASSWORD_TOO_SIMPLE: "password",
  PASSWORD_COMPROMISED: "password",
  RECOVERY_CODE_REQUIRED: "recoveryCode",
};

export function errorCodeOf(error: unknown): AuthErrorCode | null {
  if (error === null || error === undefined) {
    return null;
  }
  return isAuthApiError(error) ? error.code : "UNKNOWN_ERROR";
}

export function fieldOf(code: AuthErrorCode): AuthField | "form" {
  return FIELD_BY_CODE[code] ?? "form";
}

/** Igual que el servidor: largo en caracteres tras normalizar Unicode (NIST SP 800-63B-4). */
export const MIN_PASSWORD_LENGTH = 15;

export function passwordLength(value: string): number {
  // Se cuentan puntos de código a propósito: es lo que cuenta len() en el servidor.
  // Contar grafemas daría "15 de 15" a una contraseña que el servidor rechaza.
  // eslint-disable-next-line @typescript-eslint/no-misused-spread -- mismo criterio que el backend
  return [...value.normalize("NFKC")].length;
}

/** Validación inmediata antes de enviar una contraseña nueva. El servidor sigue siendo la autoridad. */
export function validateNewPassword(password: string): AuthErrorCode | null {
  return passwordLength(password) < MIN_PASSWORD_LENGTH ? "PASSWORD_TOO_SHORT" : null;
}
