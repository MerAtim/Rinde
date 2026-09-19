import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };

const BANCO = anAccount({ name: "Galicia sueldo" });
const EFECTIVO = anAccount({
  id: "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
  name: "Efectivo",
  kind: "cash",
});
const DOLARES = anAccount({
  id: "7f1e2d3c-4b5a-4968-8776-655443322110",
  name: "Caja dólares",
  currency: "USD",
});

const BASE = {
  ...SESSION,
  "GET /api/accounts": jsonResponse(200, [BANCO, EFECTIVO, DOLARES]),
};

async function elegir(nombre: string, opcion: RegExp) {
  const user = userEvent.setup();
  // La pantalla se carga con lazy: hay que esperar a que el campo exista.
  await user.click(await screen.findByRole("button", { name: new RegExp(nombre) }));
  await user.click(await screen.findByRole("option", { name: opcion }));
}

describe("Transferir entre cuentas", () => {
  it("manda los dos lados y vuelve a la cuenta de origen", async () => {
    let enviado: unknown = null;
    mockApi({
      ...BASE,
      "POST /api/transfers": (init) => {
        enviado = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        return jsonResponse(201, { id: "nueva" });
      },
      [`GET /api/accounts/${BANCO.id}`]: jsonResponse(200, BANCO),
      "GET /api/transactions/balances": jsonResponse(200, []),
      "GET /api/categories": jsonResponse(200, []),
    });
    renderWithProviders(<App />, { route: `/transfers/new?account=${BANCO.id}` });
    const user = userEvent.setup();

    await elegir("Hacia", /Efectivo/);
    await user.type(await screen.findByLabelText("Monto"), "50000,50");
    await user.click(screen.getByRole("button", { name: "Transferir" }));

    await screen.findByRole("heading", { name: "Galicia sueldo" });
    expect(enviado).toMatchObject({
      from_account_id: BANCO.id,
      to_account_id: EFECTIVO.id,
      // Lo escrito con coma viaja con punto, sin pasar por ningún número.
      sent: "50000.50",
      received: "50000.50",
    });
  });

  it("entre monedas distintas pide los dos montos por separado", async () => {
    mockApi(BASE);
    renderWithProviders(<App />, { route: `/transfers/new?account=${BANCO.id}` });

    // Misma moneda: un solo campo.
    await elegir("Hacia", /Efectivo/);
    expect(await screen.findByLabelText("Monto")).toBeInTheDocument();
    expect(screen.queryByLabelText("Entra")).not.toBeInTheDocument();

    // Distinta moneda: la tasa es la que le dieron a la persona, hay que pedirla.
    await elegir("Hacia", /Caja dólares/);
    expect(await screen.findByLabelText("Sale")).toBeInTheDocument();
    expect(screen.getByLabelText("Entra")).toBeInTheDocument();
  });

  it("no deja transferir una cuenta a sí misma", async () => {
    mockApi(BASE);
    renderWithProviders(<App />, { route: `/transfers/new?account=${BANCO.id}` });
    const user = userEvent.setup();

    await elegir("Hacia", /Galicia sueldo/);
    await user.type(await screen.findByLabelText("Monto"), "1000");
    await user.click(screen.getByRole("button", { name: "Transferir" }));

    expect(
      await screen.findByText("El origen y el destino tienen que ser cuentas distintas."),
    ).toBeInTheDocument();
  });

  it("con una sola cuenta explica que hacen falta dos", async () => {
    mockApi({ ...SESSION, "GET /api/accounts": jsonResponse(200, [BANCO]) });
    renderWithProviders(<App />, { route: "/transfers/new" });

    expect(
      await screen.findByRole("heading", { name: "Necesitás dos cuentas" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir otra cuenta" })).toHaveAttribute(
      "href",
      "/accounts/new",
    );
  });

  it("muestra el error del servidor junto a las cuentas", async () => {
    mockApi({
      ...BASE,
      "POST /api/transfers": jsonResponse(409, { code: "ACCOUNT_ARCHIVED" }),
    });
    renderWithProviders(<App />, { route: `/transfers/new?account=${BANCO.id}` });
    const user = userEvent.setup();

    await elegir("Hacia", /Efectivo/);
    await user.type(await screen.findByLabelText("Monto"), "1000");
    await user.click(screen.getByRole("button", { name: "Transferir" }));

    expect(await screen.findByText("Una cuenta archivada no envía ni recibe.")).toBeInTheDocument();
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi(BASE);
    const { container } = renderWithProviders(<App />, {
      route: `/transfers/new?account=${BANCO.id}`,
    });

    await screen.findByRole("heading", { name: "Transferir entre cuentas" });

    await expectNoA11yViolations(container);
  });
});
