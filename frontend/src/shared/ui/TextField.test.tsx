import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { TextField } from "./TextField";

describe("TextField", () => {
  it("asocia la etiqueta y la ayuda al campo", async () => {
    const user = userEvent.setup();
    render(<TextField label="Monto" prefix="$" description="Usá coma para los centavos." />);

    const input = screen.getByLabelText("Monto");
    await user.type(input, "48.320,50");

    expect(input).toHaveValue("48.320,50");
    expect(input).toHaveAccessibleDescription("Usá coma para los centavos.");
  });

  it("muestra el error, lo asocia al campo y lo marca como inválido", () => {
    render(<TextField label="Monto" errorMessage="Ingresá un monto mayor a 0." />);

    const input = screen.getByLabelText("Monto");

    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Ingresá un monto mayor a 0.");
  });

  it("no tiene problemas de accesibilidad, con y sin error", async () => {
    const { container } = render(
      <div>
        <TextField label="Descripción" description="Por ejemplo: supermercado" />
        <TextField label="Monto" errorMessage="Ingresá un monto mayor a 0." />
      </div>,
    );

    await expectNoA11yViolations(container);
  });
});
