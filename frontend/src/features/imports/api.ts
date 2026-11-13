import { createApiClient, type TransportErrorCode } from "../../shared/api/http";
import type { components } from "../../shared/api/schema";

export type ImportBatch = components["schemas"]["BatchResponse"];
export type BatchLine = components["schemas"]["BatchLineResponse"];
export type LineStatus = BatchLine["status"];
export type LineProblem = components["schemas"]["LineProblem"];
export type ConfirmResult = components["schemas"]["ConfirmResponse"];
export type Choice = components["schemas"]["ChoiceRequest"];

/**
 * Cómo leer el CSV. Viaja como un campo JSON del formulario, así que no está
 * en el esquema OpenAPI: es el espejo de `CsvLayoutRequest` del backend.
 */
export interface CsvLayout {
  delimiter: Delimiter;
  encoding: Encoding;
  decimal_mark: "comma" | "dot";
  date_order: "dmy" | "iso";
  has_header: boolean;
  date_column: number;
  description_column: number;
  amount:
    { kind: "signed"; column: number } | { kind: "debit_credit"; debit: number; credit: number };
}

export const DELIMITERS = [";", ",", "\t"] as const;
export type Delimiter = (typeof DELIMITERS)[number];
export const ENCODINGS = ["utf-8", "windows-1252"] as const;
export type Encoding = (typeof ENCODINGS)[number];

/** Lo mismo que acepta el servidor (ADR-0023): se avisa antes de subir. */
export const MAX_FILE_BYTES = 1024 * 1024;

/** Códigos estables que devuelve la API de importación. */
const SERVER_CODES = [
  "IMPORT_FILE_TOO_LARGE",
  "IMPORT_TOO_MANY_LINES",
  "IMPORT_FILE_EMPTY",
  "IMPORT_ENCODING_INVALID",
  "IMPORT_LAYOUT_INVALID",
  "IMPORT_NOTHING_READABLE",
  "IMPORT_BATCH_NOT_FOUND",
  "IMPORT_LINE_NOT_FOUND",
  "IMPORT_RULE_PATTERN_INVALID",
  "REQUEST_TOO_LARGE",
  "ACCOUNT_NOT_FOUND",
  "ACCOUNT_ARCHIVED",
  "CATEGORY_NOT_FOUND",
  "CATEGORY_KIND_MISMATCH",
  "TRANSACTION_ALREADY_IMPORTED",
  "NOT_AUTHENTICATED",
  "CSRF_REJECTED",
] as const;

export type ImportServerCode = (typeof SERVER_CODES)[number];
export type ImportErrorCode = ImportServerCode | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isImportsApiError = api.isError;

export async function uploadBatch(
  accountId: string,
  file: File,
  layout: CsvLayout,
): Promise<ImportBatch> {
  const form = new FormData();
  form.append("account_id", accountId);
  form.append("layout", JSON.stringify(layout));
  form.append("file", file, file.name);
  const response = await api.postForm("/api/imports", form);
  return (await response.json()) as ImportBatch;
}

export async function fetchBatch(id: string, signal: AbortSignal): Promise<ImportBatch> {
  const response = await api.get(`/api/imports/${encodeURIComponent(id)}`, signal);
  return (await response.json()) as ImportBatch;
}

export async function confirmBatch(id: string, lines: Choice[]): Promise<ConfirmResult> {
  const response = await api.post(`/api/imports/${encodeURIComponent(id)}/confirm`, { lines });
  return (await response.json()) as ConfirmResult;
}

export async function discardBatch(id: string): Promise<void> {
  await api.delete(`/api/imports/${encodeURIComponent(id)}`);
}
