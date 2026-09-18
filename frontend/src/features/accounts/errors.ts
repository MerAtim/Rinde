import {
  ACCOUNT_NAME_MAX_LENGTH,
  type AccountErrorCode,
  type AccountKind,
  type Currency,
  isAccountsApiError,
  isCurrencyAllowed,
} from "./api";

export type AccountField = "name";

// Cada error aparece junto al campo que lo causa; el resto, arriba del formulario.
const FIELD_BY_CODE: Partial<Record<AccountErrorCode, AccountField>> = {
  ACCOUNT_NAME_REQUIRED: "name",
  ACCOUNT_NAME_INVALID: "name",
};

export function errorCodeOf(error: unknown): AccountErrorCode | null {
  if (error === null || error === undefined) {
    return null;
  }
  return isAccountsApiError(error) ? error.code : "UNKNOWN_ERROR";
}

export function fieldOf(code: AccountErrorCode): AccountField | "form" {
  return FIELD_BY_CODE[code] ?? "form";
}

/** Largo como lo cuenta el servidor: puntos de código tras normalizar y recortar. */
export function nameLength(name: string): number {
  // eslint-disable-next-line @typescript-eslint/no-misused-spread -- mismo criterio que len() en el backend
  return [...name.normalize("NFC").trim()].length;
}

/** Validación inmediata antes de enviar un nombre. El servidor sigue siendo la autoridad. */
export function validateName(name: string): AccountErrorCode | null {
  const length = nameLength(name);
  if (length === 0) {
    return "ACCOUNT_NAME_REQUIRED";
  }
  return length > ACCOUNT_NAME_MAX_LENGTH ? "ACCOUNT_NAME_INVALID" : null;
}

export function validateNewAccount(
  name: string,
  kind: AccountKind,
  currency: Currency,
): AccountErrorCode | null {
  return (
    validateName(name) ??
    (isCurrencyAllowed(kind, currency) ? null : "ACCOUNT_CURRENCY_NOT_ALLOWED")
  );
}
