import {
  type DefaultOptions,
  hashKey,
  MutationCache,
  QueryCache,
  QueryClient,
} from "@tanstack/react-query";

import type { Session } from "./features/auth/api";

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
  forgetDataOfOtherUsers(client);
  return client;
}

const SESSION_HASH = hashKey(SESSION_QUERY_KEY);

/**
 * Cuando cambia quién está en la sesión (cierra, ingresa otra persona, se pasa
 * de una demo a una cuenta propia), se descarta todo lo que estaba en caché: lo
 * de la persona anterior no tiene que aparecer, ni por un instante, a la nueva.
 */
function forgetDataOfOtherUsers(client: QueryClient): void {
  let current: string | null | undefined;
  client.getQueryCache().subscribe((event) => {
    if (event.type !== "updated" || event.query.queryHash !== SESSION_HASH) {
      return;
    }
    const session = event.query.state.data as Session | null | undefined;
    if (session === undefined) {
      return;
    }
    const next = session?.username ?? null;
    if (current !== undefined && next !== current) {
      client.removeQueries({ predicate: (query) => query.queryHash !== SESSION_HASH });
    }
    current = next;
  });
}
