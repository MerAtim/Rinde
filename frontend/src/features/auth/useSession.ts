import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { isTransientError } from "../../shared/api/http";
import { fetchSession, type Session } from "./api";

export const SESSION_QUERY_KEY = ["auth", "session"] as const;

/**
 * Render Free duerme la API tras 15 minutos y despertarla tarda hasta un
 * minuto. Mientras el error sea pasajero se sigue esperando, con espera
 * exponencial y un techo: 1, 2, 4, 8 y después cada 10 segundos. Diez
 * reintentos suman unos 75 segundos más lo que tarde cada pedido; si para
 * entonces no respondió, ya no es el arranque y se muestra el error.
 */
export const WAKE_MAX_RETRIES = 10;
const WAKE_MAX_DELAY_MS = 10_000;

export function retryWhileWaking(failureCount: number, error: unknown): boolean {
  return isTransientError(error) && failureCount < WAKE_MAX_RETRIES;
}

export function wakeRetryDelay(failureCount: number): number {
  return Math.min(1000 * 2 ** failureCount, WAKE_MAX_DELAY_MS);
}

/** La sesión actual. `data` es null cuando no hay ninguna abierta. */
export function useSession() {
  return useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: ({ signal }) => fetchSession(signal),
    staleTime: 60_000,
    retry: retryWhileWaking,
    retryDelay: wakeRetryDelay,
  });
}

export function useSetSession(): (session: Session | null) => void {
  const queryClient = useQueryClient();
  return useCallback(
    (session: Session | null) => {
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
    },
    [queryClient],
  );
}
