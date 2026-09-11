import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

const PASSPHRASE = "mi gato come fideos los martes";

async function signIn(password: string) {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Nombre de usuario"), "mechi");
  await user.type(screen.getByLabelText("Contraseña"), password);
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

describe("Ingresar", () => {
  it("avisa que los datos no son correctos sin decir cuál", async () => {
    mockApi({
      "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }),
      "POST /api/auth/login": jsonResponse(401, { code: "INVALID_CREDENTIALS" }),
    });
    renderWithProviders(<App />, { route: "/login" });

    await signIn("otra frase bastante larga");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El usuario o la contraseña no son correctos.",
    );
  });

  it("con datos correctos abre la sesión y lleva al inicio", async () => {
    let signedIn = false;
    mockApi({
      "GET /api/auth/me": () =>
        signedIn
          ? jsonResponse(200, { username: "mechi" })
          : jsonResponse(401, { code: "NOT_AUTHENTICATED" }),
      "POST /api/auth/login": () => {
        signedIn = true;
        return new Response(null, { status: 204 });
      },
    });
    renderWithProviders(<App />, { route: "/login" });

    await signIn(PASSPHRASE);

    expect(await screen.findByText("Hola, mechi")).toBeInTheDocument();
  });

  it("permite ver la contraseña para revisar lo escrito", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }) });
    renderWithProviders(<App />, { route: "/login" });
    const user = userEvent.setup();

    const password = await screen.findByLabelText("Contraseña");
    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Mostrar la contraseña" }));

    expect(password).toHaveAttribute("type", "text");
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi({ "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }) });
    const { container } = renderWithProviders(<App />, { route: "/login" });

    await screen.findByRole("heading", { name: "Ingresá a Rinde" });

    await expectNoA11yViolations(container);
  });
});
