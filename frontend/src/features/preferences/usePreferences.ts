import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
    onSuccess: (preferences) => {
      queryClient.setQueryData(preferenceKeys.all, preferences);
    },
  });
}
