import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dashboardKeys } from "../dashboard/useDashboard";
import { fetchPreferences, type Preferences, updatePreferences } from "./api";

export const preferenceKeys = {
  all: ["preferences"] as const,
};

export function usePreferences() {
  return useQuery({
    queryKey: preferenceKeys.all,
    queryFn: ({ signal }) => fetchPreferences(signal),
  });
}

/**
 * No es optimista: cambiar la moneda de referencia cambia los equivalentes de
 * toda la app, y es mejor que aparezcan una vez que el servidor la guardó.
 */
export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Preferences) => updatePreferences(input),
    onSuccess: async (preferences) => {
      queryClient.setQueryData(preferenceKeys.all, preferences);
      // El dashboard está en la moneda y el dólar de referencia: hay que rehacerlo.
      await queryClient.invalidateQueries({ queryKey: dashboardKeys.all });
    },
  });
}
