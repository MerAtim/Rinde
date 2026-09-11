import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { fetchSession, type Session } from "./api";

export const SESSION_QUERY_KEY = ["auth", "session"] as const;

/** La sesión actual. `data` es null cuando no hay ninguna abierta. */
export function useSession() {
  return useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: ({ signal }) => fetchSession(signal),
    staleTime: 60_000,
    retry: false,
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
