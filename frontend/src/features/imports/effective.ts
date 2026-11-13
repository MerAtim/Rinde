import type { BatchLine } from "./api";
import { applies, patternFrom } from "./rules";

/** Lo que la persona decidió de una línea en la vista previa. */
export interface LineChoice {
  included: boolean;
  /** La categoría que eligió a mano, o `null` si no tocó la propuesta. */
  categoryId: string | null;
  /** El texto a recordar tal como lo escribe, o `null` si no recuerda nada. */
  remember: string | null;
}

export interface Effective {
  categoryId: string | null;
  /** La regla que la eligió, del servidor o recordada en este lote. */
  rule: string | null;
}

/** El signo se lee del string: restar en el frontend sería aritmética de dinero. */
export function isExpense(line: BatchLine): boolean {
  return line.amount.amount.startsWith("-");
}

interface LocalRule {
  pattern: string;
  categoryId: string;
  expense: boolean;
}

/**
 * La categoría de cada línea, calculada en cada render: lo elegido a mano
 * gana; después, la regla más específica recordada en este lote; si no, lo
 * que propuso el servidor. Una regla nueva le gana a una guardada si es al
 * menos igual de específica, porque recordar el mismo texto la reemplaza
 * (ADR-0024).
 */
export function effectiveCategories(
  lines: readonly BatchLine[],
  choices: Readonly<Record<number, LineChoice>>,
): Map<number, Effective> {
  const local: LocalRule[] = [];
  for (const line of lines) {
    const choice = choices[line.number];
    const pattern =
      choice?.included && choice.remember !== null ? patternFrom(choice.remember) : null;
    const categoryId = choice?.categoryId ?? line.category_id;
    if (pattern && categoryId) {
      local.push({ pattern, categoryId, expense: isExpense(line) });
    }
  }
  const result = new Map<number, Effective>();
  for (const line of lines) {
    const chosen = choices[line.number]?.categoryId;
    if (chosen) {
      result.set(line.number, { categoryId: chosen, rule: null });
      continue;
    }
    const best = local
      .filter((rule) => rule.expense === isExpense(line) && applies(rule.pattern, line.description))
      .sort((a, b) => b.pattern.length - a.pattern.length || a.pattern.localeCompare(b.pattern))[0];
    if (best && (line.rule === null || best.pattern.length >= line.rule.length)) {
      result.set(line.number, { categoryId: best.categoryId, rule: best.pattern });
    } else {
      result.set(line.number, { categoryId: line.category_id, rule: line.rule });
    }
  }
  return result;
}
