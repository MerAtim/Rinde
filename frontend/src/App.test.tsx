import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { expectNoA11yViolations } from "./test/a11y";
import { renderWithProviders } from "./test/render";

describe("App", () => {
  it("presenta la marca y su pregunta central", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderWithProviders(<App />);

    expect(screen.getByText("Rinde")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "¿Me rinde el sueldo?" }),
    ).toBeInTheDocument();
  });

  it("no tiene problemas de accesibilidad en la pantalla completa", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    const { container } = renderWithProviders(<App />);

    await expectNoA11yViolations(container);
  });
});
