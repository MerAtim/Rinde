import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { Select } from "./Select";

const OPTIONS = [
  { id: "super", label: "Supermercado" },
  { id: "alquiler", label: "Alquiler" },
];

describe("Select", () => {
  it("elige una opción con el mouse", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Select
        label="Categoría"
        placeholder="Elegí una"
        options={OPTIONS}
        value={null}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Categoría/ }));
    await user.click(await screen.findByRole("option", { name: "Alquiler" }));

    expect(onChange).toHaveBeenCalledWith("alquiler");
  });

  it("muestra el error junto al campo", () => {
    render(
      <Select
        label="Categoría"
        placeholder="Elegí una"
        options={OPTIONS}
        value={null}
        onChange={vi.fn()}
        errorMessage="Elegí una categoría."
      />,
    );

    expect(screen.getByRole("button", { name: /Categoría/ })).toHaveAccessibleDescription(
      "Elegí una categoría.",
    );
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(
      <Select
        label="Categoría"
        placeholder="Elegí una"
        options={OPTIONS}
        value="super"
        onChange={vi.fn()}
        description="La usás para agrupar tus gastos."
      />,
    );

    await expectNoA11yViolations(container);
  });
});
