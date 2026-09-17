import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import type { OpenAccountInput } from "./api";
import { anAccount } from "./fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };

describe("Abrir una cuenta", () => {
  it("abre la cuenta y vuelve a la lista con una confirmación", async () => {
    const created = anAccount({ name: "Lemon", kind: "crypto_wallet", currency: "BTC" });
    let sent: unknown = null;
    let opened = false;
    mockApi({
      ...SESSION,
      "POST /api/accounts": (init) => {
        sent = typeof init?.body === "string" ? JSON.parse(init.body) : null;
        opened = true;
        return jsonResponse(201, created);
      },
      "GET /api/accounts": () => jsonResponse(200, opened ? [created] : []),
    });
    renderWithProviders(<App />, { route: "/accounts/new" });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Nombre"), "Lemon");
    await user.click(screen.getByRole("radio", { name: "Billetera cripto" }));
    await user.click(screen.getByRole("radio", { name: "Bitcoin (BTC)" }));
    await user.click(screen.getByRole("button", { name: "Abrir cuenta" }));

    expect(await screen.findByRole("link", { name: /Lemon/ })).toBeInTheDocument();
    expect(screen.getByText("Abriste la cuenta «Lemon».")).toHaveAttribute("role", "status");
    expect(sent).toEqual({
      name: "Lemon",
      kind: "crypto_wallet",
      currency: "BTC",
    } satisfies OpenAccountInput);
  });

  it("no ofrece Bitcoin fuera de una billetera cripto", async () => {
    mockApi(SESSION);
    renderWithProviders(<App />, { route: "/accounts/new" });
    const user = userEvent.setup();

    const bitcoin = await screen.findByRole("radio", { name: "Bitcoin (BTC)" });
    expect(bitcoin).toBeDisabled();

    await user.click(screen.getByRole("radio", { name: "Billetera cripto" }));
    await user.click(bitcoin);
    expect(bitcoin).toBeChecked();

    // Al volver a un banco, Bitcoin deja de valer y la moneda vuelve a pesos.
    await user.click(screen.getByRole("radio", { name: "Banco" }));
    expect(bitcoin).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Pesos argentinos (ARS)" })).toBeChecked();
  });

  it("pide un nombre antes de enviar", async () => {
    const fetchMock = mockApi(SESSION);
    renderWithProviders(<App />, { route: "/accounts/new" });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Nombre"), "   ");
    await user.click(screen.getByRole("button", { name: "Abrir cuenta" }));

    expect(screen.getByLabelText("Nombre")).toHaveAccessibleDescription(
      "Escribí un nombre para la cuenta.",
    );
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("muestra junto al campo el nombre que rechaza el servidor", async () => {
    mockApi({
      ...SESSION,
      "POST /api/accounts": jsonResponse(422, { code: "ACCOUNT_NAME_INVALID" }),
    });
    renderWithProviders(<App />, { route: "/accounts/new" });
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText("Nombre"), "Galicia");
    await user.click(screen.getByRole("button", { name: "Abrir cuenta" }));

    expect(
      await screen.findByText("Usá hasta 60 caracteres, sin caracteres invisibles."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Abrir una cuenta" })).toBeInTheDocument();
  });

  it("sin conexión, lo avisa arriba del formulario y conserva lo cargado", async () => {
    mockApi(SESSION);
    renderWithProviders(<App />, { route: "/accounts/new" });
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Nombre"), "Galicia");

    // A partir de acá la red se cae: fetch rechaza, como hace el navegador.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await user.click(screen.getByRole("button", { name: "Abrir cuenta" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No hay conexión con Rinde. Revisá tu internet y probá de nuevo.",
    );
    expect(screen.getByLabelText("Nombre")).toHaveValue("Galicia");
  });

  it("no tiene problemas de accesibilidad", async () => {
    mockApi(SESSION);
    const { container } = renderWithProviders(<App />, { route: "/accounts/new" });

    await screen.findByRole("heading", { name: "Abrir una cuenta" });

    await expectNoA11yViolations(container);
  });
});
