import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { RadioCardGroup } from "./RadioCardGroup";

const OPTIONS = [
  { id: "cash", label: "Efectivo", icon: "cash" },
  { id: "bank", label: "Banco", icon: "bank" },
  { id: "credit_card", label: "Tarjeta", icon: "credit-card" },
] as const;

describe("RadioCardGroup", () => {
  it("informa la opción elegida con el mouse", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RadioCardGroup label="Tipo" options={OPTIONS} value="cash" onChange={onChange} />);

    await user.click(screen.getByRole("radio", { name: "Banco" }));

    expect(onChange).toHaveBeenCalledWith("bank");
  });

  it("se recorre con las flechas del teclado", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RadioCardGroup label="Tipo" options={OPTIONS} value="cash" onChange={onChange} />);

    await user.tab();
    expect(screen.getByRole("radio", { name: "Efectivo" })).toHaveFocus();
    await user.keyboard("{ArrowRight}");

    expect(onChange).toHaveBeenCalledWith("bank");
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(
      <RadioCardGroup label="Tipo" options={OPTIONS} value="bank" onChange={vi.fn()} />,
    );

    expect(screen.getByRole("radiogroup", { name: "Tipo" })).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });
});
