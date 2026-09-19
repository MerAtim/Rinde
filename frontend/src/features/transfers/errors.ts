import { isTransfersApiError, type TransferErrorCode } from "./api";

export type TransferField = "sent" | "received" | "date" | "description" | "accounts";

// Cada error aparece junto al campo que lo causa; el resto, arriba del formulario.
const FIELD_BY_CODE: Partial<Record<TransferErrorCode, TransferField>> = {
  SENT_REQUIRED: "sent",
  RECEIVED_REQUIRED: "received",
  AMOUNT_INVALID: "sent",
  AMOUNT_TOO_PRECISE: "sent",
  TRANSFER_AMOUNT_NOT_POSITIVE: "sent",
  TRANSFER_CURRENCY_MISMATCH: "sent",
  DATE_REQUIRED: "date",
  TRANSFER_DATE_IN_FUTURE: "date",
  TRANSACTION_DESCRIPTION_INVALID: "description",
  ACCOUNTS_REQUIRED: "accounts",
  TRANSFER_SAME_ACCOUNT: "accounts",
  ACCOUNT_NOT_FOUND: "accounts",
  ACCOUNT_ARCHIVED: "accounts",
};

export function errorCodeOf(error: unknown): TransferErrorCode | null {
  if (error === null || error === undefined) {
    return null;
  }
  return isTransfersApiError(error) ? error.code : "UNKNOWN_ERROR";
}

export function fieldOf(code: TransferErrorCode): TransferField | "form" {
  return FIELD_BY_CODE[code] ?? "form";
}
