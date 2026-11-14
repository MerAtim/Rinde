import { isRecurringApiError, type RecurringErrorCode } from "./api";

export type RecurringField = "account" | "amount" | "category" | "date" | "description" | "form";

// Cada error aparece junto al campo que lo causa; el resto, arriba del formulario.
const FIELD_BY_CODE: Partial<Record<RecurringErrorCode, RecurringField>> = {
  ACCOUNT_NOT_FOUND: "account",
  ACCOUNT_ARCHIVED: "account",
  AMOUNT_REQUIRED: "amount",
  AMOUNT_INVALID: "amount",
  AMOUNT_TOO_PRECISE: "amount",
  TRANSACTION_AMOUNT_NOT_POSITIVE: "amount",
  TRANSACTION_CURRENCY_MISMATCH: "amount",
  CATEGORY_REQUIRED: "category",
  CATEGORY_NOT_FOUND: "category",
  CATEGORY_KIND_MISMATCH: "category",
  DATE_REQUIRED: "date",
  RECURRING_START_OUT_OF_RANGE: "date",
  TRANSACTION_DESCRIPTION_INVALID: "description",
};

export function errorCodeOf(error: unknown): RecurringErrorCode | null {
  if (error === null || error === undefined) return null;
  return isRecurringApiError(error) ? error.code : "UNKNOWN_ERROR";
}

export function fieldOf(code: RecurringErrorCode): RecurringField | "form" {
  return FIELD_BY_CODE[code] ?? "form";
}
