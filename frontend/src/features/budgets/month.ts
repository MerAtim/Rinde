/**
 * El mes de la pantalla de presupuestos vive en la URL (ADR-0020): un enlace a
 * octubre muestra octubre, y Atrás vuelve al mes anterior que se miró.
 *
 * El mes en curso no se escribe: `/budgets` sigue siendo "este mes" el mes que
 * viene. Un valor que no es un mes, o que todavía no empezó, se ignora.
 */

const MONTH = /^(\d{4})-(0[1-9]|1[0-2])$/;

/** El mes elegido, AAAA-MM, o `null` si es el mes en curso. */
export function monthFrom(params: URLSearchParams, current: string): string | null {
  const month = params.get("month");
  if (!month || !MONTH.test(month) || month >= current) {
    return null;
  }
  return month;
}

export function withMonth(
  params: URLSearchParams,
  month: string,
  current: string,
): URLSearchParams {
  const next = new URLSearchParams(params);
  if (month >= current) {
    next.delete("month");
  } else {
    next.set("month", month);
  }
  return next;
}

/** Aritmética de calendario, no de dinero: mover un mes para adelante o para atrás. */
export function shiftMonth(month: string, delta: number): string {
  const match = MONTH.exec(month);
  if (!match) {
    throw new Error(`no es un mes: ${month}`);
  }
  const index = Number(match[1]) * 12 + Number(match[2]) - 1 + delta;
  const year = Math.floor(index / 12);
  return `${String(year)}-${String((index % 12) + 1).padStart(2, "0")}`;
}
