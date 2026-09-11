import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  it("empieza en oscuro, pasa a claro y recuerda la elección", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole("button", { name: "Cambiar a modo claro" }));

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("rinde.theme")).toBe("light");
    expect(screen.getByRole("button", { name: "Cambiar a modo oscuro" })).toBeInTheDocument();
  });

  it("vuelve a oscuro", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await user.click(screen.getByRole("button", { name: "Cambiar a modo claro" }));
    await user.click(screen.getByRole("button", { name: "Cambiar a modo oscuro" }));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("rinde.theme")).toBe("dark");
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(<ThemeToggle />);

    await expectNoA11yViolations(container);
  });
});
