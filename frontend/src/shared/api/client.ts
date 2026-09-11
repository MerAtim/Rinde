import type { components } from "./schema";

// Tipos generados desde el contrato OpenAPI del backend: no se escriben a mano.
export type ReadinessResponse = components["schemas"]["ReadinessResponse"];

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`La API respondió con el estado ${String(status)}`);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Consulta si la API puede atender pedidos. Un 503 también trae el detalle en el cuerpo. */
export async function fetchReadiness(signal: AbortSignal): Promise<ReadinessResponse> {
  const response = await fetch("/api/health/ready", {
    headers: { Accept: "application/json" },
    signal,
  });
  if (response.status !== 200 && response.status !== 503) {
    throw new ApiError(response.status);
  }
  return (await response.json()) as ReadinessResponse;
}
