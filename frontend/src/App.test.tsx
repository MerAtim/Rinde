import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { renderWithProviders } from "./test/render";

describe("App", () => {
  it("presenta la aplicación y su pregunta central", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );

    renderWithProviders(<App />);

    expect(screen.getByRole("heading", { level: 1, name: "Rinde" })).toBeInTheDocument();
    expect(screen.getByText("¿Me rinde el sueldo?")).toBeInTheDocument();
  });
});
