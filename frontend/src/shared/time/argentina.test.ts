import { describe, expect, it } from "vitest";

import { argentineDay, argentineMonth } from "./argentina";

describe("día de Argentina", () => {
  it("a las 23 de Buenos Aires sigue siendo ese día, aunque en UTC ya sea el siguiente", () => {
    expect(argentineDay("2026-12-01T02:00:00Z")).toBe("2026-11-30");
  });

  it("acepta un Date", () => {
    expect(argentineDay(new Date("2026-11-11T15:00:00Z"))).toBe("2026-11-11");
  });

  it("el mes también sigue a Buenos Aires", () => {
    expect(argentineMonth(new Date("2027-01-01T01:30:00Z"))).toBe("2026-12");
  });
});
