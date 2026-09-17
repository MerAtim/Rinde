import { type DefaultOptions, MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { SESSION_QUERY_KEY } from "./features/auth/useSession";
import { ApiRequestError } from "./shared/api/http";

const MAX_RETRIES = 3;

/** Un 4xx no cambia por insistir: solo se reintenta la red caída o un 5xx. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiRequestError && error.status >= 400 && error.status < 500) {
    return false;
  }
  return failureCount < MAX_RETRIES;
}

/**
 * El cliente de datos de la app. Si cualquier pedido informa que la sesión
 * terminó, se descarta la sesión en caché y la ruta protegida lleva a ingresar:
 * cada pantalla no tiene que acordarse de hacerlo.
 */
export function createQueryClient(defaultOptions: DefaultOptions = {}): QueryClient {
  function onError(error: unknown) {
    if (error instanceof ApiRequestError && error.code === "NOT_AUTHENTICATED") {
      client.setQueryData(SESSION_QUERY_KEY, null);
    }
  }

  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      ...defaultOptions,
      queries: { retry: shouldRetry, ...defaultOptions.queries },
    },
  });
  return client;
}
