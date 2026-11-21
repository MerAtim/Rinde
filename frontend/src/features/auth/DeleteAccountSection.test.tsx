import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";

const PASSPHRASE = "mi gato come fideos los martes";
const PREFERENCES = {
  "GET /api/preferences": jsonResponse(200, { reference_currency: "ARS", rate_type: "mep" }),
};

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  return input instanceof URL ? input.href : input.url;
}

function deleteRequests(fetchMock: ReturnType<typeof mockApi>): number {
  return fetchMock.mock.calls.filter(
    ([input, init]) => init?.method === "POST" && urlOf(input).endsWith("/api/auth/me/delete"),
  ).length;
}

async function openDialog() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Borrar mi cuenta" }));
  const dialog = await screen.findByRole("alertdialog", {
    name: "¿Borrar tu cuenta para siempre?",
  });
  return { user, dialog };
}

describe("Borrar la cuenta", () => {
  it("con la contraseña correcta borra la cuenta y lleva a ingresar con un aviso", async () => {
    let sent: unknown = null;
    let deleted = false;
    mockApi({
      ...PREFERENCES,
      "GET /api/auth/me": () =>
        deleted
          ? jsonResponse(401, { code: "NOT_AUTHENTICATED" })
          : jsonResponse(200, { username: "mechi" }),
      "POST /api/auth/me/delete": (init) => {
        sent = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        deleted = true;
        return new Response(null, { status: 204 });
      },
    });
    renderWithProviders(<App />, { route: "/preferences" });

    const { user, dialog } = await openDialog();
    await user.type(within(dialog).getByLabelText("Contraseña"), PASSPHRASE);
    await user.click(within(dialog).getByRole("button", { name: "Borrar para siempre" }));

    expect(await screen.findByRole("heading", { name: "Ingresá a Rinde" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Borramos tu cuenta y todos tus datos.");
    expect(sent).toEqual({ password: PASSPHRASE });
  });

  it("sin contraseña no envía nada y pide escribirla", async () => {
    const fetchMock = mockApi({
      ...PREFERENCES,
      "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
    });
    renderWithProviders(<App />, { route: "/preferences" });

    const { user, dialog } = await openDialog();
    await user.click(within(dialog).getByRole("button", { name: "Borrar para siempre" }));

    expect(
      await within(dialog).findByText("Ingresá tu contraseña para confirmar."),
    ).toBeInTheDocument();
    expect(deleteRequests(fetchMock)).toBe(0);
  });

  it("con una contraseña equivocada avisa junto al campo y no cierra la sesión", async () => {
    mockApi({
      ...PREFERENCES,
      "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
      "POST /api/auth/me/delete": jsonResponse(401, { code: "INVALID_CREDENTIALS" }),
    });
    renderWithProviders(<App />, { route: "/preferences" });

    const { user, dialog } = await openDialog();
    await user.type(within(dialog).getByLabelText("Contraseña"), "otra frase bastante larga");
    await user.click(within(dialog).getByRole("button", { name: "Borrar para siempre" }));

    expect(await within(dialog).findByText("La contraseña no es correcta.")).toBeInTheDocument();
    // La sesión sigue abierta: el diálogo queda para corregir la contraseña.
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Contraseña")).toBeEnabled();
  });

  it("cancelar cierra el diálogo sin borrar nada", async () => {
    const fetchMock = mockApi({
      ...PREFERENCES,
      "GET /api/auth/me": jsonResponse(200, { username: "mechi" }),
    });
    renderWithProviders(<App />, { route: "/preferences" });

    const { user, dialog } = await openDialog();
    await user.click(within(dialog).getByRole("button", { name: "Cancelar" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(deleteRequests(fetchMock)).toBe(0);
  });

  it("en una demo explica que se borra sola y no ofrece borrarla", async () => {
    mockApi({
      ...PREFERENCES,
      "GET /api/auth/me": jsonResponse(200, {
        username: "demo-abc123",
        demo_expires_at: "2099-01-01T00:00:00Z",
      }),
    });
    renderWithProviders(<App />, { route: "/preferences" });

    expect(
      await screen.findByText("Esta demo se borra sola, con todo lo que tiene, cuando vence."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Borrar mi cuenta" })).not.toBeInTheDocument();
  });

  it("el diálogo no tiene problemas de accesibilidad", async () => {
    mockApi({ ...PREFERENCES, "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) });
    renderWithProviders(<App />, { route: "/preferences" });

    const { dialog } = await openDialog();

    await expectNoA11yViolations(dialog);
  });
});
