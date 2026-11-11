import { readFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

import { mockSession } from "./session";

/**
 * El resumen del inicio en un navegador de verdad (ADR-0020).
 *
 * jsdom no tiene canvas ni motor de maquetado: lo que se prueba acá es lo que
 * solo se ve dibujado. Que los gráficos se dibujen, que nada se salga de la
 * pantalla en un teléfono, que la tabla reemplace al gráfico y que Chart.js no
 * choque con la política de seguridad de contenido.
 *
 * `vite preview` no manda las cabeceras de producción: la CSP se toma del mismo
 * archivo que despliega Cloudflare y se agrega a la página a mano.
 */

const CSP = (() => {
  const headers = readFileSync(new URL("../public/_headers", import.meta.url), "utf8");
  const match = /Content-Security-Policy: (.+)/.exec(headers);
  if (!match?.[1]) {
    throw new Error("public/_headers no tiene Content-Security-Policy");
  }
  return match[1].trim();
})();

async function withProductionCsp(page: Page): Promise<void> {
  await page.route(
    (url) => !url.pathname.startsWith("/api/"),
    async (route) => {
      if (route.request().resourceType() !== "document") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      await route.fulfill({
        response,
        headers: { ...response.headers(), "content-security-policy": CSP },
      });
    },
  );
  // Las violaciones no cortan la página: se juntan para revisarlas al final.
  await page.addInitScript(() => {
    const found: string[] = [];
    Object.assign(window, { cspViolations: found });
    document.addEventListener("securitypolicyviolation", (event) => {
      found.push(`${event.violatedDirective}: ${event.blockedURI || "inline"}`);
    });
  });
}

const IDIOMAS = [
  {
    codigo: "es-AR",
    nombre: "español",
    titulo: "Resumen",
    patrimonio: "Patrimonio",
    flujo: "Ingresos y gastos",
    tabla: "Tabla",
  },
  {
    codigo: "en-US",
    nombre: "inglés",
    titulo: "Overview",
    patrimonio: "Net worth",
    flujo: "Income and expenses",
    tabla: "Table",
  },
] as const;

for (const idioma of IDIOMAS) {
  test.describe(`en ${idioma.nombre}`, () => {
    test.use({ locale: idioma.codigo });

    for (const ancho of [360, 1440]) {
      test(`a ${String(ancho)} px los gráficos se dibujan y nada se desborda`, async ({ page }) => {
        await page.setViewportSize({ width: ancho, height: 900 });
        await withProductionCsp(page);
        await mockSession(page);
        await page.goto("/");

        await expect(page.getByRole("heading", { level: 1, name: idioma.titulo })).toBeVisible();
        const canvases = page.locator("canvas");
        await expect(canvases).toHaveCount(2);
        await page.evaluate(() => document.fonts.ready);

        // Un canvas que Chart.js no pudo dibujar queda con alto cero.
        for (const canvas of await canvases.all()) {
          const caja = await canvas.boundingBox();
          expect(caja?.height ?? 0).toBeGreaterThan(100);
          expect(caja?.width ?? 0).toBeGreaterThan(200);
        }

        const desborde = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(desborde).toBeLessThanOrEqual(0);

        const violaciones = await page.evaluate(
          () => (window as unknown as { cspViolations: string[] }).cspViolations,
        );
        expect(violaciones).toEqual([]);
      });
    }

    test("a 360 px las tablas equivalentes entran sin desplazar la página", async ({ page }) => {
      await page.setViewportSize({ width: 360, height: 900 });
      await mockSession(page);
      await page.goto("/");

      for (const nombre of [idioma.patrimonio, idioma.flujo]) {
        const tarjeta = page.getByRole("region", { name: nombre, exact: true });
        await tarjeta.getByRole("radio", { name: idioma.tabla }).click();
        await expect(tarjeta.getByRole("table")).toBeVisible();
        await expect(tarjeta.locator("canvas")).toHaveCount(0);
      }
      await page.evaluate(() => document.fonts.ready);

      const desborde = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(desborde).toBeLessThanOrEqual(0);
    });
  });
}

test.describe("filtros", () => {
  test.use({ locale: "es-AR" });

  test("los filtros quedan en la URL y sobreviven a recargar", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mockSession(page);
    const pedidos: string[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname === "/api/dashboard") pedidos.push(url.search);
    });
    await page.goto("/");

    await page.getByRole("button", { name: /Período/ }).click();
    await page.getByRole("option", { name: "Últimos 12 meses" }).click();
    await expect(page).toHaveURL(/[?&]months=12\b/);

    await page.reload();
    await expect(page.getByRole("button", { name: /Período/ })).toContainText("Últimos 12 meses");
    expect(pedidos.at(-1)).toMatch(/^\?from=\d{4}-\d{2}$/);
  });
});
