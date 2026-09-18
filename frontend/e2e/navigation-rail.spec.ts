import { expect, test } from "@playwright/test";

import { mockSession } from "./session";

/**
 * La navegación principal no se puede recortar.
 *
 * Esto existe por un bug real: la etiqueta "Movimientos" era más ancha que el
 * rail de 88 px, se salía hacia la izquierda y el borde de la ventana la
 * cortaba. Ningún test lo vio, porque jsdom no tiene motor de maquetado y no
 * mide nada. Se encontró mirando una captura de pantalla.
 *
 * Lo que se verifica no es "Movimientos entra", que se rompería con cualquier
 * palabra nueva, sino la invariante: nada de lo que hay dentro de una opción
 * puede salirse de su caja. Vale para el rail vertical y para la barra inferior
 * de pantallas chicas, donde un desborde pisaría a la opción vecina.
 *
 * Se prueban los dos idiomas porque el ancho depende de la palabra: "Movimientos"
 * y "Transactions" no miden lo mismo, y alcanza con que una no entre.
 */

// El rail vertical aparece desde 600 px (ventana mediana de Material 3); abajo
// de eso es una barra inferior. Se prueban los dos lados del corte.
const ANCHOS = [360, 599, 600, 768, 1440];

const TOLERANCIA = 0.5; // Redondeos subpíxel del navegador.

const IDIOMAS = [
  { codigo: "es-AR", nombre: "español", navegacion: "Navegación principal" },
  { codigo: "en-US", nombre: "inglés", navegacion: "Main navigation" },
] as const;

for (const idioma of IDIOMAS) {
  test.describe(`en ${idioma.nombre}`, () => {
    test.use({ locale: idioma.codigo });

    for (const ancho of ANCHOS) {
      test(`a ${String(ancho)} px ninguna opción de la navegación se desborda`, async ({
        page,
      }) => {
        await page.setViewportSize({ width: ancho, height: 900 });
        await mockSession(page);
        await page.goto("/accounts");

        const rail = page.getByRole("navigation", { name: idioma.navegacion });
        await expect(rail).toBeVisible();
        // La tipografía propia cambia el ancho del texto: sin esperarla se mide
        // la de reserva y el test diría que entra cuando no entra.
        await page.evaluate(() => document.fonts.ready);

        const desbordes = await rail.evaluate((nav, tolerancia) => {
          const fuera: string[] = [];
          for (const opcion of nav.querySelectorAll("li")) {
            const caja = opcion.getBoundingClientRect();
            for (const hijo of opcion.querySelectorAll("*")) {
              const suya = hijo.getBoundingClientRect();
              if (suya.width === 0) continue;
              if (suya.left < caja.left - tolerancia || suya.right > caja.right + tolerancia) {
                const texto = hijo.textContent.trim();
                fuera.push(
                  `"${texto}" ocupa ${suya.left.toFixed(0)}..${suya.right.toFixed(0)} ` +
                    `y su opción va de ${caja.left.toFixed(0)} a ${caja.right.toFixed(0)}`,
                );
              }
            }
          }
          return fuera;
        }, TOLERANCIA);

        expect(desbordes).toEqual([]);
      });
    }

    test("la página no se puede desplazar en horizontal", async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 900 });
      await mockSession(page);
      await page.goto("/accounts");
      await expect(page.getByRole("navigation", { name: idioma.navegacion })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);

      const desborde = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(desborde).toBeLessThanOrEqual(0);
    });
  });
}
