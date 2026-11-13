import { describe, expect, it } from "vitest";

import { effectiveCategories, type LineChoice } from "./effective";
import { aLine } from "./fixtures";

const OTHER = "otros";
const FOOD = "super";
const KIOSK = "kiosco";

function choice(overrides: Partial<LineChoice> = {}): LineChoice {
  return { included: true, categoryId: null, remember: null, ...overrides };
}

describe("effectiveCategories", () => {
  const coto = aLine({ number: 2, description: "COTO SUC 12", category_id: OTHER, rule: null });
  const cotoAgain = aLine({
    number: 3,
    description: "Cotó digital",
    category_id: OTHER,
    rule: null,
  });
  const salary = aLine({
    number: 4,
    description: "COTO SUELDO",
    amount: { amount: "1000.00", currency: "ARS" },
    category_id: "otros-ingresos",
    rule: null,
  });

  it("sin nada elegido, queda lo que propuso el servidor", () => {
    const result = effectiveCategories([coto], { 2: choice() });

    expect(result.get(2)).toEqual({ categoryId: OTHER, rule: null });
  });

  it("recordar un texto toma las otras líneas del mismo tipo que lo contienen", () => {
    const result = effectiveCategories([coto, cotoAgain, salary], {
      2: choice({ categoryId: FOOD, remember: "Coto" }),
      3: choice(),
      4: choice(),
    });

    expect(result.get(2)).toEqual({ categoryId: FOOD, rule: null });
    expect(result.get(3)).toEqual({ categoryId: FOOD, rule: "coto" });
    // Un ingreso no toma una regla de gastos.
    expect(result.get(4)).toEqual({ categoryId: "otros-ingresos", rule: null });
  });

  it("lo elegido a mano le gana a una regla", () => {
    const result = effectiveCategories([coto, cotoAgain], {
      2: choice({ categoryId: FOOD, remember: "coto" }),
      3: choice({ categoryId: KIOSK }),
    });

    expect(result.get(3)).toEqual({ categoryId: KIOSK, rule: null });
  });

  it("gana la más específica, y un texto inválido no cuenta", () => {
    const digital = aLine({
      number: 5,
      description: "COTO DIGITAL",
      category_id: OTHER,
      rule: null,
    });
    const result = effectiveCategories([coto, digital, cotoAgain], {
      2: choice({ categoryId: FOOD, remember: "coto" }),
      5: choice({ categoryId: KIOSK, remember: "coto digital" }),
      3: choice({ remember: "co" }),
    });

    expect(result.get(3)).toEqual({ categoryId: KIOSK, rule: "coto digital" });
  });

  it("una regla guardada más específica le gana a una nueva más corta", () => {
    const saved = aLine({
      number: 3,
      description: "COTO DIGITAL",
      category_id: KIOSK,
      rule: "coto digital",
    });

    const result = effectiveCategories([coto, saved], {
      2: choice({ categoryId: FOOD, remember: "coto" }),
      3: choice(),
    });

    expect(result.get(3)).toEqual({ categoryId: KIOSK, rule: "coto digital" });
  });

  it("una línea afuera no recuerda nada", () => {
    const result = effectiveCategories([coto, cotoAgain], {
      2: choice({ included: false, categoryId: FOOD, remember: "coto" }),
      3: choice(),
    });

    expect(result.get(3)).toEqual({ categoryId: OTHER, rule: null });
  });
});
