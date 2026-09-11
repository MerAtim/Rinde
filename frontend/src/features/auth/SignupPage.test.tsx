import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

const PASSPHRASE = "mi gato come fideos los martes";
const CODE = "ABCD-EFGH-JKMN-PQRS-TVWX";
const NO_SESSION = { "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }) };

async function fillAndSubmit(username: string, password: string) {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Nombre de usuario"), username);
  await user.type(screen.getByLabelText("Contraseña"), password);
  await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
  return user;
}

describe("Crear cuenta", () => {
  it("frena una contraseña corta sin llamar a la API", async () => {
    const fetchMock = mockApi(NO_SESSION);
    renderWithProviders(<App />, { route: "/signup" });

    await fillAndSubmit("mechi", "corta");

    expect(screen.getByLabelText("Contraseña")).toHaveAccessibleDescription(
      /al menos 15 caracteres/,
    );
    expect(fetchMock).not.toHaveBeenCalledWith("/api/auth/register", expect.anything());
  });

  it("muestra el error de la API junto al campo que lo causa", async () => {
    mockApi({
      ...NO_SESSION,
      "POST /api/auth/register": jsonResponse(409, { code: "USERNAME_TAKEN" }),
    });
    renderWithProviders(<App />, { route: "/signup" });

    await fillAndSubmit("mechi", PASSPHRASE);

    expect(await screen.findByLabelText("Nombre de usuario")).toHaveAccessibleDescription(
      "Ese nombre ya está en uso. Probá con otro.",
    );
  });

  it("muestra el código y no deja seguir hasta confirmar que se guardó", async () => {
    mockApi({
      ...NO_SESSION,
      "POST /api/auth/register": jsonResponse(201, { username: "mechi", recovery_code: CODE }),
    });
    renderWithProviders(<App />, { route: "/signup" });

    const user = await fillAndSubmit("mechi", PASSPHRASE);

    expect(
      await screen.findByRole("heading", { name: "Guardá tu código de recuperación" }),
    ).toBeInTheDocument();
    expect(screen.getByText(CODE)).toBeInTheDocument();
    const continueButton = screen.getByRole("button", { name: "Continuar" });
    expect(continueButton).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Copiar" }));
    expect(await navigator.clipboard.readText()).toBe(CODE);

    await user.click(screen.getByRole("checkbox", { name: "Guardé el código en un lugar seguro" }));
    await user.click(continueButton);

    expect(await screen.findByText("Hola, mechi")).toBeInTheDocument();
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi(NO_SESSION);
    const { container } = renderWithProviders(<App />, { route: "/signup" });

    await screen.findByRole("heading", { name: "Creá tu cuenta" });

    await expectNoA11yViolations(container);
  });
});
