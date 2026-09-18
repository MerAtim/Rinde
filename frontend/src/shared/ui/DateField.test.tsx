import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { DateField } from "./DateField";

describe("DateField", () => {
  it("informa la fecha elegida en formato ISO", () => {
    const onChange = vi.fn();
    render(<DateField label="Fecha" value="2026-09-18" onChange={onChange} />);

    // El calendario del sistema escribe el valor; el formato visible es el del
    // navegador, pero el valor siempre es ISO.
    fireEvent.change(screen.getByLabelText("Fecha"), { target: { value: "2026-09-11" } });

    expect(onChange).toHaveBeenLastCalledWith("2026-09-11");
  });

  it("muestra el error junto al campo", () => {
    render(
      <DateField
        label="Fecha"
        value=""
        onChange={vi.fn()}
        errorMessage="Elegí una fecha que no sea futura."
      />,
    );

    const field = screen.getByLabelText("Fecha");
    expect(field).toHaveAccessibleDescription("Elegí una fecha que no sea futura.");
    expect(field).toBeInvalid();
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(
      <DateField
        label="Fecha"
        value="2026-09-18"
        onChange={vi.fn()}
        description="Cuándo pasó, no cuándo lo anotás."
      />,
    );

    await expectNoA11yViolations(container);
  });
});
