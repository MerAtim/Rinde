/**
 * Claves de consulta de presupuestos, en un archivo sin dependencias: las
 * importan los módulos que invalidan presupuestos (movimientos, preferencias)
 * sin traer, ni crear un ciclo con, las pantallas de presupuestos.
 */
export const budgetKeys = {
  all: ["budgets"] as const,
  month: (month: string | null) => ["budgets", month ?? "current"] as const,
};
