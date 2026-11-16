import { randomUUID } from "node:crypto";

import { expect, type Page, test } from "@playwright/test";

/**
 * Los tres flujos críticos contra el entorno completo (ADR-0013, decisión 3).
 *
 * * Registrarse y volver a entrar: sin esto nadie usa la app.
 * * Abrir una cuenta y registrar un gasto: lo que la app hace todos los días,
 *   con el saldo calculado por el backend y guardado en la base.
 * * Probar la demo: la puerta de entrada de quien visita el portfolio, y lo
 *   único que prueba la siembra contra PostgreSQL real.
 *
 * Cada prueba crea su propia cuenta, con un nombre que no se repite: no
 * dependen unas de otras ni de corridas anteriores.
 */

function credenciales() {
  const id = randomUUID().replaceAll("-", "");
  return {
    usuario: `e2e.${id.slice(0, 20)}`,
    // Larga, propia de esta corrida y sin el nombre de usuario adentro.
    frase: `una frase de prueba distinta ${id.slice(20)}`,
  };
}

/** Adentro de la app: el inicio, con la navegación que solo existe con sesión. */
async function enElInicio(page: Page): Promise<void> {
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("navigation", { name: "Navegación principal" })).toBeVisible();
}

async function registrarse(page: Page): Promise<{ usuario: string; frase: string }> {
  const datos = credenciales();
  await page.goto("/signup");
  await page.getByLabel("Nombre de usuario").fill(datos.usuario);
  await page.getByLabel("Contraseña", { exact: true }).fill(datos.frase);
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  await expect(
    page.getByRole("heading", { name: "Guardá tu código de recuperación" }),
  ).toBeVisible();
  await expect(page.getByText(/^[0-9A-Z]{4}(-[0-9A-Z]{4}){4}$/)).toBeVisible();
  // React Aria oculta el input: se toca la etiqueta, como lo hace una persona.
  await page.getByText("Guardé el código en un lugar seguro").click();
  await expect(
    page.getByRole("checkbox", { name: "Guardé el código en un lugar seguro" }),
  ).toBeChecked();
  await page.getByRole("button", { name: "Continuar" }).click();
  await enElInicio(page);
  return datos;
}

async function ingresar(page: Page, usuario: string, frase: string): Promise<void> {
  await page.getByLabel("Nombre de usuario").fill(usuario);
  await page.getByLabel("Contraseña", { exact: true }).fill(frase);
  await page.getByRole("button", { name: "Ingresar" }).click();
}

test("registrarse, guardar el código, salir y volver a entrar", async ({ page }) => {
  const { usuario, frase } = await registrarse(page);

  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page.getByRole("heading", { name: "Ingresá a Rinde" })).toBeVisible();

  await ingresar(page, usuario, "otra frase que no es la de esta cuenta");
  await expect(page.getByRole("alert")).toHaveText("El usuario o la contraseña no son correctos.");

  await ingresar(page, usuario, frase);
  await enElInicio(page);
  // Una cuenta nueva no tiene nada que resumir: el inicio lo dice.
  await expect(
    page.getByRole("heading", { name: "Todavía no hay nada que resumir" }),
  ).toBeVisible();
});

test("abrir una cuenta, registrar un gasto y ver el saldo", async ({ page }) => {
  await registrarse(page);

  await page.goto("/accounts/new");
  await page.getByLabel("Nombre").fill("Banco de la prueba");
  await page.getByText("Banco", { exact: true }).click();
  await page.getByRole("radio", { name: "Pesos argentinos (ARS)" }).click();
  await page.getByRole("button", { name: "Abrir cuenta" }).click();
  await expect(page.getByText("Abriste la cuenta «Banco de la prueba».").first()).toBeVisible();

  await page.goto("/transactions/new");
  await page.getByLabel("Monto").fill("15.300,50");
  await page.getByRole("button", { name: /Categoría/ }).click();
  await page.getByRole("option", { name: "Supermercado" }).click();
  await page.getByRole("button", { name: "Registrar" }).click();

  // El monto sale con signo y flecha, formateado en es-AR por el frontend.
  await expect(
    page
      .getByRole("main")
      .getByText(/15\.300,50/)
      .first(),
  ).toBeVisible();

  // El saldo lo calcula el backend: después de recargar, sigue ahí.
  await page.goto("/accounts");
  await page.reload();
  const cuenta = page.getByRole("main").getByText("Banco de la prueba").first();
  await expect(cuenta).toBeVisible();
  await expect(
    page
      .getByRole("main")
      .getByText(/15\.300,50/)
      .first(),
  ).toBeVisible();
});

test("probar la demo sin registrarse", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Probar la demo" }).click();

  // Sembrar tres meses de datos lleva un momento más que entrar.
  await expect(page.getByRole("heading", { level: 1, name: "Resumen" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("region", { name: "Cuenta demo" })).toBeVisible();

  // El súper del mes quedó cerca de su tope: la demo muestra la alerta.
  await page.goto("/budgets");
  await expect(page.getByText("Cerca del tope")).toBeVisible();

  // Lo generado solo: una cuota y un recurrente, con su marca en la lista.
  await page.goto("/transactions");
  await expect(page.getByText(/Cuota \d de 6/).first()).toBeVisible();
  await expect(page.getByText(/ · Recurrente$/).first()).toBeVisible();
});
