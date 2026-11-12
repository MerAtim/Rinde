import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchAlerts, markAlertsRead } from "./api";
import { alertKeys } from "./keys";

/**
 * Las alertas las dispara el servidor al guardar un gasto (ADR-0022). Movimientos
 * invalida esta consulta, y la respuesta del gasto llega con la alerta ya guardada.
 */
export function useAlerts() {
  return useQuery({
    queryKey: alertKeys.all,
    queryFn: ({ signal }) => fetchAlerts(signal),
  });
}

export function useMarkAlertsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: markAlertsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: alertKeys.all }),
  });
}
