import { isTransactionsApiError, type TransactionErrorCode } from "./api";

export type TransactionField = "amount" | "category" | "date" | "description" | "account";

// Cada error aparece junto al campo que lo causa; el resto, arriba del formulario.
const FIELD_BY_CODE: Partial<Record<TransactionErrorCode, TransactionField>> = {
  AMOUNT_REQUIRED: "amount",
  AMOUNT_INVALID: "amount",
  AMOUNT_TOO_PRECISE: "amount",
  TRANSACTION_AMOUNT_NOT_POSITIVE: "amount",
  TRANSACTION_CURRENCY_MISMATCH: "amount",
  DATE_REQUIRED: "date",
  TRANSACTION_DATE_IN_FUTURE: "date",
  TRANSACTION_DESCRIPTION_INVALID: "description",
  CATEGORY_REQUIRED: "category",
  CATEGORY_NOT_FOUND: "category",
  CATEGORY_KIND_MISMATCH: "category",
  ACCOUNT_NOT_FOUND: "account",
  ACCOUNT_ARCHIVED: "account",
};

export function errorCodeOf(error: unknown): TransactionErrorCode | null {
  if (error === null || error === undefined) {
    return null;
  }
  return isTransactionsApiError(error) ? error.code : "UNKNOWN_ERROR";
}

export function fieldOf(code: TransactionErrorCode): TransactionField | "form" {
  return FIELD_BY_CODE[code] ?? "form";
}

/**
 * Pasa lo que se escribió a un string decimal con punto, que es lo que espera la
 * API. No se hace aritmética: solo se cambia la coma por punto y se limpian los
 * separadores de miles, porque en Argentina se escribe 15.300,50.
 */
export function toDecimalString(typed: string): string | null {
  const cleaned = typed
    .trim()
    .replace(/\s/g, "")
    .replace(/\.(?=\d{3}(\D|$))/g, "")
    .replace(",", ".");
  if (!cleaned) {
    return null;
  }
  return /^\d+(\.\d+)?$/.test(cleaned) ? cleaned : null;
}

/** Valida antes de enviar. El servidor sigue siendo la autoridad. */
export function validateAmount(typed: string): TransactionErrorCode | null {
  if (!typed.trim()) {
    return "AMOUNT_REQUIRED";
  }
  const decimal = toDecimalString(typed);
  if (decimal === null) {
    return "AMOUNT_INVALID";
  }
  // Cero escrito de cualquier forma: 0, 0.00, .0. Sin convertir a número: en el
  // frontend no se hace aritmética de dinero (ADR-0002).
  const isZero = /^0*(\.0*)?$/.test(decimal);
  return isZero ? "TRANSACTION_AMOUNT_NOT_POSITIVE" : null;
}
