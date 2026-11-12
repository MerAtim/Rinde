import { describe, expect, it } from "vitest";

import { monthFrom, shiftMonth, withMonth } from "./month";

const CURRENT = "2026-11";

describe("el mes de presupuestos en la URL", () => {
  it("sin mes, o con el mes en curso, es el mes en curso", () => {
    expect(monthFrom(new URLSearchParams(""), CURRENT)).toBeNull();
    expect(monthFrom(new URLSearchParams("month=2026-11"), CURRENT)).toBeNull();
  });

  it("lee un mes que ya pasó", () => {
    expect(monthFrom(new URLSearchParams("month=2026-09"), CURRENT)).toBe("2026-09");
  });

  it.each(["2026-12", "2026-13", "2026-1", "septiembre", "2026-09-01"])(
    "ignora %s: no es un mes o todavía no empezó",
    (month) => {
      expect(monthFrom(new URLSearchParams({ month }), CURRENT)).toBeNull();
    },
  );

  it("no escribe el mes en curso y conserva los demás parámetros", () => {
    const params = new URLSearchParams("month=2026-09&otro=1");

    expect(withMonth(params, "2026-11", CURRENT).toString()).toBe("otro=1");
    expect(withMonth(params, "2026-10", CURRENT).toString()).toBe("month=2026-10&otro=1");
  });

  it("mueve meses cruzando el año", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2025-12", 1)).toBe("2026-01");
    expect(shiftMonth("2026-11", -12)).toBe("2025-11");
  });
});
