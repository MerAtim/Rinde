import {
  argbFromHex,
  Hct,
  hexFromArgb,
  MaterialDynamicColors,
  SchemeTonalSpot,
  TonalPalette,
} from "@material/material-color-utilities";
import { describe, expect, it } from "vitest";

import tokensCss from "./tokens.css?raw";

// Controla que tokens.css siga derivando de Material You (ADR-0006) y que
// cumpla los contrastes mínimos. Si alguien cambia un color a mano, este test falla.

const SEED = "#33D6C4";
const SEMANTIC_SEEDS = { income: "#90DA4F", expense: "#FF6B5B", warning: "#F5B83D" } as const;

type Theme = "dark" | "light";

function block(theme: Theme): string {
  const selector = theme === "dark" ? ":root {" : ':root[data-theme="light"] {';
  const start = tokensCss.indexOf(selector);
  if (start === -1) throw new Error(`No se encontró el bloque ${selector}`);
  return tokensCss.slice(start, tokensCss.indexOf("\n}", start));
}

function token(theme: Theme, name: string): string {
  const match = new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})\\s*;`).exec(block(theme));
  if (!match?.[1]) throw new Error(`Falta el token --${name} en el tema ${theme}`);
  return match[1].toUpperCase();
}

function hex(argb: number): string {
  return hexFromArgb(argb).toUpperCase();
}

function luminance(color: string): number {
  const channels = [1, 3, 5].map((i) => {
    const value = parseInt(color.slice(i, i + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  const [r = 0, g = 0, b = 0] = channels;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (light + 0.05) / (dark + 0.05);
}

const colors = new MaterialDynamicColors();

const DERIVED_ROLES = {
  primary: colors.primary(),
  "on-primary": colors.onPrimary(),
  "primary-container": colors.primaryContainer(),
  "on-primary-container": colors.onPrimaryContainer(),
  "secondary-container": colors.secondaryContainer(),
  "on-secondary-container": colors.onSecondaryContainer(),
  "on-surface": colors.onSurface(),
  "on-surface-variant": colors.onSurfaceVariant(),
  outline: colors.outline(),
  "inverse-surface": colors.inverseSurface(),
  "inverse-on-surface": colors.inverseOnSurface(),
  "inverse-primary": colors.inversePrimary(),
  error: colors.error(),
  "on-error": colors.onError(),
  "error-container": colors.errorContainer(),
  "on-error-container": colors.onErrorContainer(),
} as const;

const SURFACES = [
  "background",
  "surface-container-lowest",
  "surface-container-low",
  "surface-container",
  "surface-container-high",
  "surface-container-highest",
];

describe.each<Theme>(["dark", "light"])("tokens del tema %s", (theme) => {
  const scheme = new SchemeTonalSpot(Hct.fromInt(argbFromHex(SEED)), theme === "dark", 0);

  it.each(Object.entries(DERIVED_ROLES))("--md-sys-color-%s deriva de la semilla", (name, role) => {
    expect(token(theme, `md-sys-color-${name}`)).toBe(hex(role.getArgb(scheme)));
  });

  it.each(Object.entries(SEMANTIC_SEEDS))("--rinde-%s sale de su paleta tonal", (name, seed) => {
    const hct = Hct.fromInt(argbFromHex(seed));
    const palette = TonalPalette.fromHueAndChroma(hct.hue, Math.max(hct.chroma, 48));
    const [text, container, onContainer] = theme === "dark" ? [80, 30, 90] : [40, 90, 30];
    expect(token(theme, `rinde-${name}`)).toBe(hex(palette.tone(text)));
    expect(token(theme, `rinde-${name}-container`)).toBe(hex(palette.tone(container)));
    expect(token(theme, `rinde-on-${name}-container`)).toBe(hex(palette.tone(onContainer)));
  });

  it("no usa negro puro en ninguna superficie", () => {
    for (const surface of SURFACES) {
      expect(token(theme, `md-sys-color-${surface}`)).not.toBe("#000000");
    }
  });

  it.each(["on-surface", "on-surface-variant", "primary"])(
    "--md-sys-color-%s contrasta al menos 4,5:1 sobre todas las superficies",
    (name) => {
      for (const surface of SURFACES) {
        expect(
          contrast(token(theme, `md-sys-color-${name}`), token(theme, `md-sys-color-${surface}`)),
        ).toBeGreaterThanOrEqual(4.5);
      }
    },
  );

  it.each(["rinde-income", "rinde-expense", "rinde-warning", "md-sys-color-error"])(
    "--%s contrasta al menos 4,5:1 sobre las superficies de contenido",
    (name) => {
      for (const surface of ["background", "surface-container", "surface-container-high"]) {
        expect(
          contrast(token(theme, name), token(theme, `md-sys-color-${surface}`)),
        ).toBeGreaterThanOrEqual(4.5);
      }
    },
  );

  it("las marcas de gráficos contrastan al menos 3:1", () => {
    for (const surface of ["surface-container", "surface-container-high"]) {
      expect(
        contrast(token(theme, "rinde-chart-mark"), token(theme, `md-sys-color-${surface}`)),
      ).toBeGreaterThanOrEqual(3);
    }
  });
});
