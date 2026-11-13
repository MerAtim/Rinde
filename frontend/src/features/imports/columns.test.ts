import { describe, expect, it } from "vitest";

import { guessColumns } from "./columns";

describe("guessColumns", () => {
  it("reconoce los títulos de un extracto, con o sin tildes", () => {
    expect(
      guessColumns(["Fecha", "Descripción", "Referencia", "Débitos", "Créditos", "Saldo"]),
    ).toEqual({
      date: 0,
      description: 1,
      amount: null,
      debit: 3,
      credit: 4,
    });
  });

  it("y los de una columna con signo", () => {
    expect(guessColumns(["Concepto", "FECHA OPERACION", "Importe"])).toEqual({
      date: 1,
      description: 0,
      amount: 2,
      debit: null,
      credit: null,
    });
  });

  it("sin títulos reconocibles no propone nada", () => {
    expect(guessColumns(["15/10/2026", "COTO", "-10,00"])).toEqual({
      date: null,
      description: null,
      amount: null,
      debit: null,
      credit: null,
    });
  });
});
