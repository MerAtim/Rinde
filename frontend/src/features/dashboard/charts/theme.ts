import {
  BarElement,
  CategoryScale,
  Chart,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { useSyncExternalStore } from "react";

// Solo las piezas que se usan: Chart.js descarta el resto del bundle.
Chart.register(BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip);

/**
 * El canvas no lee variables de CSS: los colores se toman de los tokens del
 * tema activo (ADR-0006) y se vuelven a leer cuando el tema cambia.
 */
export interface ChartTheme {
  mark: string;
  grid: string;
  income: string;
  expense: string;
  ink: string;
  inkMuted: string;
  surface: string;
  tooltip: string;
  font: string;
  markRadius: number;
  tooltipRadius: number;
  gap: number;
}

function subscribe(onChange: () => void): () => void {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => {
    observer.disconnect();
  };
}

function themeName(): string {
  return document.documentElement.dataset.theme ?? "dark";
}

function readTheme(): ChartTheme {
  const style = getComputedStyle(document.documentElement);
  const token = (name: string) => style.getPropertyValue(`--${name}`).trim();
  const pixels = (name: string) => Number.parseFloat(token(name)) || 0;
  return {
    mark: token("rinde-chart-mark"),
    grid: token("rinde-chart-grid"),
    income: token("rinde-income"),
    expense: token("rinde-expense"),
    ink: token("md-sys-color-on-surface"),
    inkMuted: token("md-sys-color-on-surface-variant"),
    surface: token("md-sys-color-surface-container"),
    tooltip: token("md-sys-color-surface-container-highest"),
    font: token("md-ref-typeface-plain"),
    markRadius: pixels("rinde-shape-chart-mark"),
    tooltipRadius: pixels("rinde-shape-badge"),
    gap: pixels("rinde-space-2"),
  };
}

// Los tokens de un tema no cambian mientras la página está abierta: se leen una
// vez por tema. Además, `useSyncExternalStore` necesita el mismo objeto mientras
// nada cambió, o vuelve a dibujar sin fin.
let cached: { name: string; theme: ChartTheme } | null = null;

function snapshot(): ChartTheme {
  const name = themeName();
  if (cached?.name !== name) {
    cached = { name, theme: readTheme() };
  }
  return cached.theme;
}

export function useChartTheme(): ChartTheme {
  return useSyncExternalStore(subscribe, snapshot);
}

/**
 * Lo común a los gráficos del dashboard: sin animación (los datos no se mueven
 * por adorno, docs/design-system.md), grilla de un píxel y tooltip con los
 * colores de la app. La leyenda va en HTML, fuera del canvas. Son piezas sin
 * tipo de gráfico: cada uno las arma en sus propias opciones.
 */
export function chartBase(theme: ChartTheme) {
  const font = { family: theme.font, size: 12 };
  return {
    common: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
    } as const,
    tooltip: {
      backgroundColor: theme.tooltip,
      titleColor: theme.ink,
      bodyColor: theme.ink,
      titleFont: { ...font, weight: 600 },
      bodyFont: font,
      cornerRadius: theme.tooltipRadius,
      padding: theme.gap,
      boxPadding: theme.gap / 2,
    },
    x: {
      grid: { display: false },
      border: { display: false },
      ticks: { color: theme.inkMuted, font },
    },
    y: {
      grid: { color: theme.grid, lineWidth: 1 },
      border: { display: false },
      ticks: { color: theme.inkMuted, font, maxTicksLimit: 5 },
    },
  };
}
