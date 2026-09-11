import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

const NO_SESSION = { "GET /api/auth/me": jsonResponse(401, { code: "NOT_AUTHENTICATED" }) };

async function fillAndSubmit() {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Nombre de usuario"), "mechi");
  await user.type(screen.getByLabelText("Código de recuperación"), "abcd efgh jkmn pqrs tvwx");
  await user.type(screen.getByLabelText("Contraseña nueva"), "una frase nueva y bien larga");
  await user.click(screen.getByRole("button", { name: "Cambiar la contraseña" }));
}

describe("Recuperar la cuenta", () => {
  it("con el código correcto entrega un código nuevo", async () => {
    mockApi({
      ...NO_SESSION,
      "POST /api/auth/recover": jsonResponse(200, { recovery_code: "WXYZ-2345-6789-ABCD-EFGH" }),
    });
    renderWithProviders(<App />, { route: "/recover" });

    await fillAndSubmit();

    expect(
      await screen.findByRole("heading", { name: "Guardá tu código nuevo" }),
    ).toBeInTheDocument();
    expect(screen.getByText("El código anterior ya no sirve.")).toBeInTheDocument();
    expect(screen.getByText("WXYZ-2345-6789-ABCD-EFGH")).toBeInTheDocument();
  });

  it("no revela si falló el usuario o el código", async () => {
    mockApi({
      ...NO_SESSION,
      "POST /api/auth/recover": jsonResponse(401, { code: "RECOVERY_CODE_INVALID" }),
    });
    renderWithProviders(<App />, { route: "/recover" });

    await fillAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El usuario o el código de recuperación no son correctos.",
    );
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi(NO_SESSION);
    const { container } = renderWithProviders(<App />, { route: "/recover" });

    await screen.findByRole("heading", { name: "Recuperá tu cuenta" });

    await expectNoA11yViolations(container);
  });
});
