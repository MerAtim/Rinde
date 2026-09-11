import axe from "axe-core";
import { expect } from "vitest";

/**
 * Revisa el fragmento con axe-core, el motor de accesibilidad estándar.
 * El contraste de color se desactiva porque jsdom no calcula estilos: lo
 * controla tokens.test.ts sobre los valores reales del sistema de diseño.
 */
export async function expectNoA11yViolations(container: Element): Promise<void> {
  const results = await axe.run(container, {
    rules: { "color-contrast": { enabled: false } },
  });
  expect(results.violations.map((violation) => `${violation.id}: ${violation.help}`)).toEqual([]);
}
