import { argentineMonth } from "../../shared/time/argentina";
import type { DashboardQuery } from "./api";

/**
 * El período del dashboard, tal como viaja en la URL de la pantalla.
 *
 * La URL guarda cuántos meses mirar y no un mes fijo: un enlace a "los últimos
 * seis meses" sigue diciendo eso el mes que viene. Se lee como cualquier dato
 * de afuera: un valor que no está en la lista vuelve al de siempre.
 */

export const PERIOD_MONTHS = [3, 6, 12, 24] as const;
export type PeriodMonths = (typeof PERIOD_MONTHS)[number];

/** El mismo que usa el servidor cuando no se le pide otro (ADR-0018). */
export const DEFAULT_MONTHS: PeriodMonths = 6;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface DashboardFilters {
  months: PeriodMonths;
  /** Vacío: todas las cuentas. */
  accountId: string;
}

function isPeriodMonths(value: number): value is PeriodMonths {
  return PERIOD_MONTHS.some((months) => months === value);
}

export function filtersFrom(params: URLSearchParams): DashboardFilters {
  const months = Number(params.get("months"));
  const accountId = params.get("account") ?? "";
  return {
    months: isPeriodMonths(months) ? months : DEFAULT_MONTHS,
    accountId: UUID.test(accountId) ? accountId : "",
  };
}

/** Escribe los filtros sobre los parámetros actuales; lo que vale lo de siempre no se escribe. */
export function withFilters(params: URLSearchParams, filters: DashboardFilters): URLSearchParams {
  const updated = new URLSearchParams(params);
  if (filters.months === DEFAULT_MONTHS) {
    updated.delete("months");
  } else {
    updated.set("months", String(filters.months));
  }
  if (filters.accountId) {
    updated.set("account", filters.accountId);
  } else {
    updated.delete("account");
  }
  return updated;
}

/**
 * El primer mes de un período que termina en `current` (AAAA-MM). Es aritmética
 * de calendario, no de dinero: cuenta meses hacia atrás.
 */
export function firstMonth(current: string, months: number): string {
  const [year = 0, month = 1] = current.split("-").map(Number);
  const index = year * 12 + (month - 1) - (months - 1);
  const first = Math.floor(index / 12);
  return `${String(first)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

/** Lo que se le pide al servidor: el período por defecto no se manda, lo decide él. */
export function dashboardQuery(filters: DashboardFilters, now: Date): DashboardQuery {
  return {
    ...(filters.months === DEFAULT_MONTHS
      ? {}
      : { from: firstMonth(argentineMonth(now), filters.months) }),
    ...(filters.accountId ? { accountId: filters.accountId } : {}),
  };
}
