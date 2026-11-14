import type { CategorySpending, FlowRow, NetWorthPoint } from "../api";

/**
 * Los números que los gráficos necesitan para dibujar.
 *
 * Son las únicas conversiones de un monto a `number` en el frontend, y sirven
 * solo para ubicar una marca: el texto de cada valor (tooltip, tabla) se
 * formatea siempre desde el string del servidor (ADR-0020). Por eso cada serie
 * lleva también los montos originales.
 */
export interface Series {
  months: string[];
  values: (number | null)[];
  amounts: (string | null)[];
}

/** Un cierre sin total (faltó una cotización) queda como hueco, no como cero. */
export function netWorthSeries(points: NetWorthPoint[]): Series {
  return {
    months: points.map((point) => point.month),
    values: points.map((point) => (point.total ? Number(point.total.amount) : null)),
    amounts: points.map((point) => point.total?.amount ?? null),
  };
}

export interface FlowSeries {
  months: string[];
  income: Series;
  expense: Series;
}

/**
 * Los ingresos suben desde el cero y los gastos bajan: la posición dice qué es
 * cada barra, así que no hace falta distinguirlas por color (ADR-0020). Un mes
 * sin IPC, en pesos de hoy, queda como hueco y no como cero (ADR-0025).
 */
export function flowSeries(monthly: FlowRow[]): FlowSeries {
  const months = monthly.map((item) => item.month);
  return {
    months,
    income: {
      months,
      values: monthly.map((item) => (item.income ? Number(item.income.amount) : null)),
      amounts: monthly.map((item) => item.income?.amount ?? null),
    },
    expense: {
      months,
      values: monthly.map((item) => (item.expense ? -Number(item.expense.amount) : null)),
      amounts: monthly.map((item) => item.expense?.amount ?? null),
    },
  };
}

/** Si el período cruza de año, el eje dice el año de cada mes. */
export function spansYears(months: string[]): boolean {
  return new Set(months.map((month) => month.slice(0, 4))).size > 1;
}

/**
 * El largo de cada barra, como porcentaje de la mayor. Es geometría: el número
 * ubica la barra y nunca se muestra; el monto visible sale del string (ADR-0020).
 */
export function barWidths(spending: CategorySpending[]): number[] {
  const values = spending.map((item) => Number(item.total.amount));
  const largest = Math.max(0, ...values);
  return values.map((value) => (largest > 0 ? (value / largest) * 100 : 0));
}
