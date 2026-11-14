/**
 * Claves de consulta de los movimientos recurrentes, en un archivo sin
 * dependencias: las importa movimientos, que las invalida al borrar o editar
 * una vez generada, sin crear un ciclo con las pantallas de recurrentes.
 */
export const recurringKeys = {
  all: ["recurring"] as const,
};
