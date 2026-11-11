import { describe, expect, it } from "vitest";

import { aDashboard } from "../fixtures";
import { barWidths, flowSeries, netWorthSeries, spansYears } from "./series";

describe("series de los gráficos", () => {
  it("un cierre sin cotización queda como hueco, no como cero", () => {
    const series = netWorthSeries(aDashboard().net_worth);

    expect(series.values).toEqual([3100000, null, 3550000.75]);
    expect(series.amounts).toEqual(["3100000.00", null, "3550000.75"]);
  });

  it("los gastos se dibujan abajo del cero, pero el monto mostrado sigue siendo el del servidor", () => {
    const series = flowSeries(aDashboard().monthly);

    expect(series.income.values).toEqual([900000, 900000, 0]);
    expect(series.expense.values).toEqual([-620000, -950000, -0]);
    expect(series.expense.amounts).toEqual(["620000.00", "950000.00", "0.00"]);
  });

  it("dice el año en el eje solo si el período cruza de año", () => {
    expect(spansYears(["2026-09", "2026-11"])).toBe(false);
    expect(spansYears(["2025-12", "2026-01"])).toBe(true);
  });

  it("la barra más larga es la del mayor gasto y las demás son proporcionales", () => {
    expect(barWidths(aDashboard().spending)).toEqual([100, (42000 / 150300.5) * 100]);
  });

  it("sin gastos no hay barras que dividir por cero", () => {
    const zero = aDashboard().spending.map((item) => ({
      ...item,
      total: { ...item.total, amount: "0.00" },
    }));
    expect(barWidths(zero)).toEqual([0, 0]);
    expect(barWidths([])).toEqual([]);
  });
});
