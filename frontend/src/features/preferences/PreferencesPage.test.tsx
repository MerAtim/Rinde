import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };
const DEFAULTS = { reference_currency: "ARS", rate_type: "mep" };

describe("Preferencias", () => {
  it("se llega desde la barra superior y arranca con lo guardado", async () => {
    mockApi({ ...SESSION, "GET /api/preferences": jsonResponse(200, DEFAULTS) });
    const { container } = renderWithProviders(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("link", { name: "Preferencias" }));

    expect(await screen.findByRole("heading", { name: "Preferencias" })).toBeInTheDocument();
    // El título aparece enseguida; el formulario, cuando llegan las preferencias.
    expect(await screen.findByRole("radio", { name: "Pesos argentinos (ARS)" })).toBeChecked();
    // La ayuda explica el dólar elegido: no hace falta saber qué es el MEP.
    expect(
      screen.getByRole("button", { name: /Dólar para convertir/ }),
    ).toHaveAccessibleDescription(/sin cupo/);
    await expectNoA11yViolations(container);
  });

  it("guarda la moneda y el dólar elegidos", async () => {
    let sent: unknown = null;
    mockApi({
      ...SESSION,
      "GET /api/preferences": jsonResponse(200, DEFAULTS),
      "PUT /api/preferences": (init) => {
        sent = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        return jsonResponse(200, sent);
      },
    });
    renderWithProviders(<App />, { route: "/preferences" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("radio", { name: "Dólares (USD)" }));
    await user.click(screen.getByRole("button", { name: /Dólar para convertir/ }));
    await user.click(await screen.findByRole("option", { name: "Blue" }));
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardamos tus preferencias.")).toBeInTheDocument();
    expect(sent).toEqual({ reference_currency: "USD", rate_type: "blue" });
  });

  it("muestra el error del servidor con su texto", async () => {
    mockApi({
      ...SESSION,
      "GET /api/preferences": jsonResponse(200, DEFAULTS),
      "PUT /api/preferences": jsonResponse(403, { code: "CSRF_REJECTED" }),
    });
    renderWithProviders(<App />, { route: "/preferences" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Guardar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Recargá la página");
  });

  it("avisa si no pudo cargarlas", async () => {
    mockApi({ ...SESSION, "GET /api/preferences": jsonResponse(500, {}) });
    renderWithProviders(<App />, { route: "/preferences" });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No pudimos cargar tus preferencias.",
    );
    expect(screen.queryByRole("button", { name: "Guardar" })).not.toBeInTheDocument();
  });
});
