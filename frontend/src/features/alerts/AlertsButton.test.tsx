import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { AlertsButton } from "./AlertsButton";
import { aFeed } from "./fixtures";

describe("AlertsButton", () => {
  it("dice con palabras cuántas hay sin leer, además del badge", async () => {
    mockApi({ "GET /api/alerts": jsonResponse(200, aFeed({ unread: 2 })) });
    const { container } = renderWithProviders(<AlertsButton />);

    const link = await screen.findByRole("link", { name: "Alertas, 2 sin leer" });
    expect(link).toHaveAttribute("href", "/alerts");
    // El badge va al lado del enlace, oculto para el lector: el nombre ya lo dice.
    expect(link.parentElement).toHaveTextContent("2");
    await expectNoA11yViolations(container);
  });

  it("sin nada nuevo no muestra badge", async () => {
    mockApi({ "GET /api/alerts": jsonResponse(200, aFeed({ unread: 0 })) });
    renderWithProviders(<AlertsButton />);

    const link = await screen.findByRole("link", { name: "Alertas" });
    expect(link.parentElement).toHaveTextContent("");
  });

  it("más de 9 se resume, y el número exacto queda en el nombre", async () => {
    mockApi({ "GET /api/alerts": jsonResponse(200, aFeed({ unread: 1234 })) });
    renderWithProviders(<AlertsButton />);

    const link = await screen.findByRole("link", { name: "Alertas, 1234 sin leer" });
    expect(link.parentElement).toHaveTextContent("9+");
  });

  it("si las alertas no cargan, la campana sigue llevando a la pantalla", async () => {
    mockApi({ "GET /api/alerts": jsonResponse(500, {}) });
    renderWithProviders(<AlertsButton />);

    expect(await screen.findByRole("link", { name: "Alertas" })).toHaveAttribute("href", "/alerts");
  });
});
