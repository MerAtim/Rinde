import { Bar } from "react-chartjs-2";
import { useTranslation } from "react-i18next";

import { useAxisMoneyFormatter, useMoneyFormatter, useMonthFormatter } from "../../../i18n/format";
import type { FlowRow } from "../api";
import { flowSeries, spansYears } from "./series";
import { chartBase, useChartTheme } from "./theme";

interface FlowChartProps {
  monthly: FlowRow[];
  currency: string;
}

// Más finas que el lugar disponible: el aire entre meses también se lee.
const MAX_BAR_THICKNESS = 24;

/**
 * Ingresos y gastos de cada mes. Comparten la columna del mes, uno arriba y
 * otro abajo del cero: así se ve cuál fue más grande sin depender del color.
 */
export default function FlowChart({ monthly, currency }: FlowChartProps) {
  const { t } = useTranslation();
  const theme = useChartTheme();
  const money = useMoneyFormatter();
  const axis = useAxisMoneyFormatter();
  const monthName = useMonthFormatter();
  const series = flowSeries(monthly);
  const style = spansYears(series.months) ? "short-with-year" : "short";
  const base = chartBase(theme);
  const bar = {
    maxBarThickness: MAX_BAR_THICKNESS,
    borderRadius: theme.markRadius,
    // La base queda recta y el extremo redondeado, de los dos lados del cero.
    borderSkipped: "start" as const,
  };

  return (
    <Bar
      role="img"
      aria-label={t("dashboard.flow.chartLabel")}
      data={{
        labels: series.months.map((month) => monthName(month, style)),
        datasets: [
          {
            ...bar,
            label: t("dashboard.flow.income"),
            data: series.income.values,
            backgroundColor: theme.income,
          },
          {
            ...bar,
            label: t("dashboard.flow.expense"),
            data: series.expense.values,
            backgroundColor: theme.expense,
          },
        ],
      }}
      options={{
        ...base.common,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...base.tooltip,
            callbacks: {
              title: (items) => {
                const month = series.months[items[0]?.dataIndex ?? 0];
                return month ? monthName(month, "long") : "";
              },
              label: (item) => {
                const source = item.datasetIndex === 0 ? series.income : series.expense;
                const amount = source.amounts[item.dataIndex];
                // Un hueco no tiene barra que señalar, pero el texto no inventa un cero.
                const value =
                  amount == null ? t("dashboard.flow.noIndex") : money(amount, currency);
                return `${item.dataset.label ?? ""}: ${value}`;
              },
            },
          },
        },
        scales: {
          x: { ...base.x, stacked: true },
          y: {
            ...base.y,
            stacked: true,
            grid: {
              ...base.y.grid,
              // El cero separa lo que entró de lo que salió: va un poco más marcado.
              color: (context) => (context.tick.value === 0 ? theme.inkMuted : theme.grid),
            },
            ticks: {
              ...base.y.ticks,
              // Abajo del cero son gastos: el eje los muestra en positivo.
              callback: (value) => axis(Math.abs(Number(value)), currency),
            },
          },
        },
      }}
    />
  );
}
