/** La zona del calendario de Rinde, la misma que usa el servidor. */
export const ARGENTINA_TIME_ZONE = "America/Argentina/Buenos_Aires";

const ARGENTINE_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: ARGENTINA_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/**
 * El día de Argentina en que cae un momento, como AAAA-MM-DD (`en-CA` formatea
 * así). Es el mismo criterio que usa el servidor para decir qué día es "hoy",
 * sin importar la zona horaria del navegador.
 */
export function argentineDay(moment: string | Date): string {
  return ARGENTINE_DAY.format(typeof moment === "string" ? new Date(moment) : moment);
}

/** El mes de Argentina en que cae un momento, como AAAA-MM. */
export function argentineMonth(moment: Date): string {
  return argentineDay(moment).slice(0, 7);
}
