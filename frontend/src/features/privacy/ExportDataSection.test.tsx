import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { saveFile } from "../../shared/files/saveFile";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

vi.mock("../../shared/files/saveFile", () => ({ saveFile: vi.fn() }));

const SIGNED_IN = {
  "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
  "GET /api/preferences": jsonResponse(200, { reference_currency: "ARS", rate_type: "mep" }),
};
const EXPORT = { format_version: 1, profile: { username: "mechi" } };

function exportResponse(): Response {
  return new Response(JSON.stringify(EXPORT), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": 'attachment; filename="rinde-datos-2026-11-22.json"',
    },
  });
}

async function section(): Promise<HTMLElement> {
  renderWithProviders(<App />, { route: "/preferences" });
  return screen.findByRole("region", { name: "Descargar tus datos" });
}

describe("Descargar los datos", () => {
  beforeEach(() => {
    vi.mocked(saveFile).mockClear();
  });

  it("guarda el archivo con el nombre que da el servidor y avisa que terminó", async () => {
    mockApi({ ...SIGNED_IN, "GET /api/privacy/export": exportResponse() });
    const user = userEvent.setup();
    const view = within(await section());

    await user.click(view.getByRole("button", { name: "Descargar mis datos" }));

    expect(await view.findByRole("status")).toHaveTextContent("el archivo quedó en tus descargas");
    expect(saveFile).toHaveBeenCalledTimes(1);
    const [name, content] = vi.mocked(saveFile).mock.calls[0] ?? ["", new Blob()];
    expect(name).toBe("rinde-datos-2026-11-22.json");
    expect(JSON.parse(await content.text())).toEqual(EXPORT);
  });

  it("sin conexión avisa y no guarda nada", async () => {
    mockApi({
      ...SIGNED_IN,
      "GET /api/privacy/export": () => {
        throw new TypeError("Failed to fetch");
      },
    });
    const user = userEvent.setup();
    const view = within(await section());

    await user.click(view.getByRole("button", { name: "Descargar mis datos" }));

    expect(
      await view.findByText("No hay conexión con Rinde. Revisá tu internet y probá de nuevo."),
    ).toBeInTheDocument();
    expect(saveFile).not.toHaveBeenCalled();
  });

  it("si el servidor falla avisa con un mensaje propio, sin el detalle técnico", async () => {
    mockApi({ ...SIGNED_IN, "GET /api/privacy/export": jsonResponse(500, { code: "BOOM" }) });
    const user = userEvent.setup();
    const view = within(await section());

    await user.click(view.getByRole("button", { name: "Descargar mis datos" }));

    expect(
      await view.findByText("No pudimos preparar el archivo. Probá de nuevo en un momento."),
    ).toBeInTheDocument();
    expect(saveFile).not.toHaveBeenCalled();
  });

  it("la sección no tiene problemas de accesibilidad", async () => {
    mockApi(SIGNED_IN);

    await expectNoA11yViolations(await section());
  });
});
