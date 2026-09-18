import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

/** Simula el ancho de pantalla: `matches` responde a la consulta del marco. */
function stubWidth(isWide: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: isWide,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

describe("Marco de la app", () => {
  it("en pantallas anchas muestra el texto de cerrar sesión", async () => {
    stubWidth(true);
    mockApi({ "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) });
    renderWithProviders(<App />, { route: "/" });

    expect(await screen.findByRole("button", { name: "Cerrar sesión" })).toHaveTextContent(
      "Cerrar sesión",
    );
  });

  it("en un celular deja solo el ícono, con el mismo nombre, y cierra la sesión", async () => {
    stubWidth(false);
    mockApi({
      "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
      "POST /api/auth/logout": new Response(null, { status: 204 }),
    });
    renderWithProviders(<App />, { route: "/" });
    const user = userEvent.setup();

    const logout = await screen.findByRole("button", { name: "Cerrar sesión" });
    expect(logout.textContent).toBe("");
    await user.click(logout);

    expect(await screen.findByRole("heading", { name: "Ingresá a Rinde" })).toBeInTheDocument();
  });
});
