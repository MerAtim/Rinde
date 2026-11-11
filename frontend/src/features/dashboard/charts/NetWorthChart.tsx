import { Line } from "react-chartjs-2";
import { useTranslation } from "react-i18next";

import { useAxisMoneyFormatter, useMoneyFormatter, useMonthFormatter } from "../../../i18n/format";
import type { NetWorthPoint } from "../api";
import { netWorthSeries, spansYears } from "./series";
import { chartBase, useChartTheme } from "./theme";

interface NetWorthChartProps {
  points: NetWorthPoint[];
  currency: string;
}

/** El patrimonio al cierre de cada mes: una sola serie, sin leyenda; el título la nombra. */
export default function NetWorthChart({ points, currency }: NetWorthChartProps) {
  const { t } = useTranslation();
  const theme = useChartTheme();
  const money = useMoneyFormatter();
  const axis = useAxisMoneyFormatter();
  const monthName = useMonthFormatter();
  const series = netWorthSeries(points);
  const style = spansYears(series.months) ? "short-with-year" : "short";
  const base = chartBase(theme);

  return (
    <Line
      role="img"
      aria-label={t("dashboard.netWorth.chartLabel")}
      data={{
        labels: series.months.map((month) => monthName(month, style)),
        datasets: [
          {
            data: series.values,
            borderColor: theme.mark,
            backgroundColor: theme.mark,
            borderWidth: 2,
            borderCapStyle: "round",
            borderJoinStyle: "round",
            // Un cierre sin cotización corta la línea: no se inventa el tramo.
            spanGaps: false,
            pointRadius: 4,
            pointHoverRadius: 5,
            pointBorderColor: theme.surface,
            pointBorderWidth: 2,
            pointHitRadius: 12,
          },
        ],
      }}
      options={{
        ...base.common,
        plugins: {
          legend: { display: false },
          tooltip: {
            ...base.tooltip,
            displayColors: false,
            callbacks: {
              title: (items) => {
                const month = series.months[items[0]?.dataIndex ?? 0];
                return month ? monthName(month, "long") : "";
              },
              label: (item) => {
                const amount = series.amounts[item.dataIndex];
                return amount ? money(amount, currency) : t("dashboard.netWorth.noQuote");
              },
            },
          },
        },
        scales: {
          x: base.x,
          y: {
            ...base.y,
            ticks: { ...base.y.ticks, callback: (value) => axis(Number(value), currency) },
          },
        },
      }}
    />
  );
}
