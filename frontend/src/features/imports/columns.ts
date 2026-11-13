/**
 * Una primera propuesta de columnas, a partir de los títulos del archivo. Es
 * solo eso: queda a la vista en el formulario y la persona la confirma o la
 * cambia. El servidor nunca adivina (ADR-0023).
 */

export interface ColumnGuess {
  date: number | null;
  description: number | null;
  amount: number | null;
  debit: number | null;
  credit: number | null;
}

const PATTERNS: Record<keyof ColumnGuess, RegExp> = {
  date: /^fecha|^date/,
  description: /descrip|concepto|detalle|movimiento|description|memo/,
  amount: /importe|monto|amount/,
  debit: /debito|debe|egreso|debit/,
  credit: /credito|haber|ingreso|credit/,
};

function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

export function guessColumns(header: readonly string[]): ColumnGuess {
  const folded = header.map(fold);
  const find = (key: keyof ColumnGuess) => {
    const index = folded.findIndex((cell) => PATTERNS[key].test(cell));
    return index === -1 ? null : index;
  };
  return {
    date: find("date"),
    description: find("description"),
    amount: find("amount"),
    debit: find("debit"),
    credit: find("credit"),
  };
}
