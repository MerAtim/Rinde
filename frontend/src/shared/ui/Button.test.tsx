import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { Button, type ButtonVariant } from "./Button";

const VARIANTS: ButtonVariant[] = ["filled", "tonal", "outlined", "text"];

describe("Button", () => {
  it("ejecuta la acción con el mouse y con el teclado", async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    render(
      <Button onPress={onPress} icon="check">
        Guardar movimiento
      </Button>,
    );

    const button = screen.getByRole("button", { name: "Guardar movimiento" });
    await user.click(button);
    await user.keyboard("{Enter}");

    expect(onPress).toHaveBeenCalledTimes(2);
  });

  it("no ejecuta la acción si está deshabilitado", async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    render(
      <Button onPress={onPress} isDisabled>
        Guardar
      </Button>,
    );

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onPress).not.toHaveBeenCalled();
  });

  it("no tiene problemas de accesibilidad en ninguna variante", async () => {
    const { container } = render(
      <div>
        {VARIANTS.map((variant) => (
          <Button key={variant} variant={variant} icon="check">
            {variant}
          </Button>
        ))}
      </div>,
    );

    await expectNoA11yViolations(container);
  });
});
