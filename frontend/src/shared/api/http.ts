/** Errores que no vienen del dominio sino del camino: sin red o con una respuesta inesperada. */
export type TransportErrorCode = "NETWORK_ERROR" | "UNKNOWN_ERROR";

/** Error de la API con su código estable, para traducirlo en la pantalla. */
export class ApiRequestError<Code extends string = string> extends Error {
  readonly code: Code | TransportErrorCode;
  readonly status: number;

  constructor(code: Code | TransportErrorCode, status: number) {
    super(code);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
  }
}

// Sin este encabezado la API rechaza las acciones que cambian estado (defensa CSRF).
const CSRF_HEADER = { "X-Requested-With": "rinde" };

/**
 * Cliente para un módulo de la API. Recibe los códigos que ese módulo puede
 * devolver: cualquier otro cuerpo, aunque traiga un `code`, se informa como
 * error desconocido y no llega a la pantalla sin traducción.
 */
export function createApiClient<Code extends string>(serverCodes: readonly Code[]) {
  function isServerCode(value: unknown): value is Code {
    return serverCodes.some((code) => code === value);
  }

  async function codeFrom(response: Response): Promise<Code | "UNKNOWN_ERROR"> {
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

  async function send(path: string, init: RequestInit = {}): Promise<Response> {
    let response: Response;
    try {
      response = await fetch(path, { credentials: "same-origin", ...init });
    } catch {
      throw new ApiRequestError<Code>("NETWORK_ERROR", 0);
    }
    if (!response.ok) {
      throw new ApiRequestError<Code>(await codeFrom(response), response.status);
    }
    return response;
  }

  function get(path: string, signal?: AbortSignal): Promise<Response> {
    return send(path, { headers: { Accept: "application/json" }, ...(signal ? { signal } : {}) });
  }

  function write(
    method: "POST" | "PATCH" | "DELETE",
    path: string,
    body?: object,
    headers: Record<string, string> = {},
  ): Promise<Response> {
    return send(path, {
      method,
      headers: {
        ...CSRF_HEADER,
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  }

  /** Si el error salió de este cliente: su código es uno de este módulo o de transporte. */
  function isError(error: unknown): error is ApiRequestError<Code> {
    return (
      error instanceof ApiRequestError &&
      (isServerCode(error.code) || error.code === "NETWORK_ERROR" || error.code === "UNKNOWN_ERROR")
    );
  }

  return {
    isError,
    get,
    post: (path: string, body?: object, headers?: Record<string, string>) =>
      write("POST", path, body, headers),
    patch: (path: string, body: object) => write("PATCH", path, body),
    delete: (path: string) => write("DELETE", path),
  };
}
