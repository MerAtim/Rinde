import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { type DashboardQuery, fetchDashboard } from "./api";

export const dashboardKeys = {
  all: ["dashboard"] as const,
  detail: (query: DashboardQuery) => [...dashboardKeys.all, query] as const,
};

/**
 * El resumen del período. Al cambiar un filtro se sigue mostrando el anterior
 * hasta que llega el nuevo: sin eso, la pantalla salta a "cargando" y vuelve.
 */
export function useDashboard(query: DashboardQuery) {
  return useQuery({
    queryKey: dashboardKeys.detail(query),
    queryFn: ({ signal }) => fetchDashboard(query, signal),
    placeholderData: keepPreviousData,
  });
}
