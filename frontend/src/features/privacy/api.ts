import { createApiClient, type TransportErrorCode } from "../../shared/api/http";

/** Códigos estables que devuelve la API de privacidad. */
const SERVER_CODES = ["NOT_AUTHENTICATED"] as const;

export type PrivacyErrorCode = (typeof SERVER_CODES)[number] | TransportErrorCode;

const api = createApiClient(SERVER_CODES);

export const isPrivacyApiError = api.isError;

// Por si un intermediario se come el encabezado: el archivo se guarda igual.
const FALLBACK_FILE_NAME = "rinde-datos.json";

export interface PersonalDataFile {
  name: string;
  content: Blob;
}

/**
 * Todo lo que Rinde guarda de la persona, en un JSON (ADR-0034). Se pide con
 * `fetch` y no con un enlace directo para poder mostrar un error si falla. El
 * archivo no pasa por la caché de consultas: se guarda y se suelta.
 */
export async function downloadPersonalData(): Promise<PersonalDataFile> {
  const response = await api.get("/api/privacy/export");
  return {
    name: fileNameOf(response.headers.get("Content-Disposition")),
    content: await response.blob(),
  };
}

function fileNameOf(disposition: string | null): string {
  return /filename="([^"]+)"/.exec(disposition ?? "")?.[1] ?? FALLBACK_FILE_NAME;
}
