/**
 * La coincidencia de las reglas de categoría, del lado de la pantalla (ADR-0024).
 *
 * La que vale es la del servidor, al proponer la próxima importación. Esta
 * existe para mostrar al momento qué otras líneas del mismo lote toma una regla
 * nueva. Compara igual: sin tildes, en minúsculas y con un solo espacio, y sus
 * tests repiten los casos del backend.
 */

export const MIN_PATTERN = 3;
export const MAX_PATTERN = 60;

export function comparable(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

/** `null` si el texto no sirve como regla: muy corto o muy largo. */
export function patternFrom(raw: string): string | null {
  const pattern = comparable(raw);
  return pattern.length >= MIN_PATTERN && pattern.length <= MAX_PATTERN ? pattern : null;
}

export function applies(pattern: string, description: string | null): boolean {
  return description !== null && comparable(description).includes(pattern);
}

/**
 * Lo que se propone recordar: las dos primeras palabras, que en un extracto
 * suelen ser el comercio. La persona lo cambia antes de confirmar.
 */
export function proposedPattern(description: string | null): string {
  return (description ?? "").trim().split(/\s+/).slice(0, 2).join(" ");
}
