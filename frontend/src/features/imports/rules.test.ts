import { describe, expect, it } from "vitest";

import { applies, comparable, patternFrom, proposedPattern } from "./rules";

// Los mismos casos que backend/tests/unit/imports/test_rules.py.
describe("reglas de categoría", () => {
  it("compara sin tildes, sin mayúsculas y sin espacios de más", () => {
    expect(comparable("  Panadería   La  Esquina ")).toBe("panaderia la esquina");
    expect(patternFrom("  Panadería   La  Esquina ")).toBe("panaderia la esquina");
  });

  it("un texto muy corto o muy largo no sirve", () => {
    for (const raw of ["", "  ", "ab", "x".repeat(61)]) {
      expect(patternFrom(raw)).toBeNull();
    }
  });

  it("coincide cuando la descripción lo contiene", () => {
    expect(applies("coto", "COMPRA COTO SUC 123")).toBe(true);
    expect(applies("coto", "compra  cotó")).toBe(true);
    expect(applies("coto", "CARREFOUR")).toBe(false);
    expect(applies("coto", null)).toBe(false);
  });

  it("propone las dos primeras palabras", () => {
    expect(proposedPattern("  COTO   SUC 123 ")).toBe("COTO SUC");
    expect(proposedPattern("HABERES")).toBe("HABERES");
    expect(proposedPattern(null)).toBe("");
  });
});
