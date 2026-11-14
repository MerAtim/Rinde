/**
 * Claves de consulta de las compras en cuotas, en un archivo sin dependencias:
 * las importa movimientos, que las invalida al borrar o editar una cuota, sin
 * crear un ciclo con las pantallas de cuotas.
 */
export const installmentKeys = {
  all: ["installments"] as const,
};
