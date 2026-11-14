import { expect, test } from "@playwright/test";

import { BATCH, mockSession } from "./session";

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
  { codigo: "es-AR", nombre: "español", navegacion: "Navegación principal", dolar: "Dólar hoy" },
  { codigo: "en-US", nombre: "inglés", navegacion: "Main navigation", dolar: "Dollar today" },
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

    // El inicio tiene el resumen, con montos largos, y la tabla del dólar, con
    // dos montos por fila que no se parten; Cuentas, el equivalente de un saldo largo;
    // Presupuestos, topes con montos largos; Alertas, los mismos montos en una
    // frase; y Preferencias, el formulario. La barra superior está en todas, con la
    // campana y su badge más ancho.
    for (const ruta of [
      "/",
      "/accounts",
      "/budgets",
      "/alerts",
      "/transactions/import",
      `/imports/${BATCH.id}`,
      "/installments",
      "/preferences",
    ]) {
      test(`${ruta} no se puede desplazar en horizontal`, async ({ page }) => {
        await page.setViewportSize({ width: 360, height: 900 });
        await mockSession(page);
        await page.goto(ruta);
        await expect(page.getByRole("navigation", { name: idioma.navegacion })).toBeVisible();
        // Lo más ancho de cada pantalla tiene que estar a la vista antes de medir.
        if (ruta === "/") {
          await expect(page.getByRole("region", { name: idioma.dolar })).toBeVisible();
          await expect(page.locator("canvas").first()).toBeVisible();
        } else if (ruta === "/accounts") {
          await expect(page.getByText(/≈/)).toBeVisible();
        } else if (ruta === "/budgets") {
          await expect(page.getByRole("meter")).toHaveCount(2);
        } else if (ruta === "/alerts") {
          await expect(page.getByRole("main").getByRole("listitem")).toHaveCount(2);
        } else if (ruta === "/transactions/import") {
          await expect(page.getByRole("button", { name: /CSV|file/ })).toBeVisible();
        } else if (ruta === "/installments") {
          // La tabla de cuotas abierta: 24 filas con montos largos.
          await page.locator("summary").first().click();
          await expect(page.getByRole("table")).toBeVisible();
        } else if (ruta.startsWith("/imports/")) {
          // Tres líneas, y la que entra suma "Recordar".
          await expect(page.getByRole("checkbox")).toHaveCount(4);
        } else {
          await expect(page.getByRole("radiogroup").last()).toBeVisible();
        }
        await page.evaluate(() => document.fonts.ready);

        const desborde = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(desborde).toBeLessThanOrEqual(0);
      });
    }

    // La barra superior lleva la marca y cinco acciones. Con poco ancho, flexbox
    // las achica antes que desbordar: la página no se desplaza, pero el área que
    // se toca baja de 40 px y el badge de la campana pisa al vecino. Esto no lo
    // ve el test de arriba; por eso se mide aparte.
    for (const ancho of [360, 599]) {
      test(`a ${String(ancho)} px la barra superior entra sin achicar ni encimar sus controles`, async ({
        page,
      }) => {
        await page.setViewportSize({ width: ancho, height: 900 });
        await mockSession(page);
        await page.goto("/alerts");
        await expect(page.getByRole("link", { name: /\d+/ })).toBeVisible();
        await page.evaluate(() => document.fonts.ready);

        const problemas = await page.evaluate((tolerancia) => {
          const encontrados: string[] = [];
          const fin = document.querySelector("header")?.lastElementChild;
          if (!fin) return ["no hay acciones en la barra"];
          const cajas = Array.from(fin.children).map((hijo) => hijo.getBoundingClientRect());
          for (const boton of fin.querySelectorAll<HTMLElement>("[class*='iconButton']")) {
            const ancho = boton.getBoundingClientRect().width;
            if (ancho < 40 - tolerancia) {
              const nombre = boton.getAttribute("aria-label") ?? "";
              encontrados.push(`"${nombre}" mide ${ancho.toFixed(1)} px`);
            }
          }
          // Una acción achicada recorta lo suyo: "EN" del selector de idioma.
          for (const hijo of Array.from(fin.children)) {
            if (hijo.scrollWidth > hijo.clientWidth + tolerancia) {
              encontrados.push(
                `"${hijo.textContent.trim()}" necesita ${String(hijo.scrollWidth)} px y tiene ${String(hijo.clientWidth)}`,
              );
            }
          }
          // El badge incluido: es lo que más se acerca al vecino.
          const badge = fin.querySelector("[class*='badge']")?.getBoundingClientRect();
          const derechas = cajas.map((caja, i) =>
            i === 0 && badge ? Math.max(caja.right, badge.right) : caja.right,
          );
          for (let i = 1; i < cajas.length; i++) {
            const anterior = derechas[i - 1] ?? 0;
            const actual = cajas[i]?.left ?? 0;
            if (anterior > actual + tolerancia) {
              encontrados.push(
                `la acción ${String(i)} empieza en ${actual.toFixed(1)} y la anterior termina en ${anterior.toFixed(1)}`,
              );
            }
          }
          return encontrados;
        }, TOLERANCIA);

        expect(problemas).toEqual([]);
      });
    }
  });
}
