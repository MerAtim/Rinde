/**
 * Las primeras filas del archivo, para que la persona diga qué columna es cada
 * cosa. Solo muestra texto: la lectura que vale es la del servidor (ADR-0023).
 *
 * Sigue RFC 4180 en lo que hace falta para mostrar: comillas, separadores y
 * saltos de línea adentro de un campo, y comillas dobles escapadas.
 */

import type { Encoding } from "./api";

export const PREVIEW_ROWS = 5;

export interface CsvPreview {
  rows: string[][];
  /** La cantidad de columnas de la fila más ancha. */
  columns: number;
}

/** `null` si los bytes no son texto en esa codificación. */
export function decode(bytes: ArrayBuffer, encoding: Encoding): string | null {
  try {
    const text = new TextDecoder(encoding, { fatal: true }).decode(bytes);
    return text.includes("\u0000") ? null : text;
  } catch {
    return null;
  }
}

export function previewRows(text: string, delimiter: string, limit = PREVIEW_ROWS): CsvPreview {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  let index = 0;
  const pushRow = () => {
    row.push(field);
    field = "";
    if (row.some((cell) => cell.trim() !== "")) {
      rows.push(row);
    }
    row = [];
  };
  while (index < text.length && rows.length < limit) {
    const char = text[index] ?? "";
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"' && field === "") {
      quoted = true;
    } else if (char === delimiter) {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[index + 1] === "\n") {
        index += 1;
      }
      pushRow();
    } else {
      field += char;
    }
    index += 1;
  }
  if (rows.length < limit && (field !== "" || row.length > 0)) {
    pushRow();
  }
  return { rows, columns: Math.max(0, ...rows.map((cells) => cells.length)) };
}
