import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { SegmentedButton } from "./SegmentedButton";

const OPTIONS = [
  { id: "ars", label: "Pesos" },
  { id: "usd", label: "Dólares" },
] as const;

describe("SegmentedButton", () => {
  it("informa la opción elegida", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SegmentedButton label="Moneda" options={OPTIONS} value="ars" onChange={onChange} />);

    await user.click(screen.getByRole("radio", { name: "Dólares" }));

    expect(onChange).toHaveBeenCalledWith("usd");
  });

  it("no permite quedarse sin ninguna opción", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SegmentedButton label="Moneda" options={OPTIONS} value="ars" onChange={onChange} />);

    await user.click(screen.getByRole("radio", { name: "Pesos" }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("radio", { name: "Pesos" })).toBeChecked();
  });

  it("no deja elegir una opción deshabilitada y explica por qué", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SegmentedButton
        label="Moneda"
        isLabelVisible
        description="Bitcoin solo en billeteras cripto."
        options={[...OPTIONS, { id: "btc", label: "BTC", isDisabled: true }]}
        value="ars"
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole("radio", { name: "BTC" }));

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Moneda")).toBeVisible();
    expect(screen.getByRole("radiogroup", { name: "Moneda" })).toHaveAccessibleDescription(
      "Bitcoin solo en billeteras cripto.",
    );
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(
      <SegmentedButton label="Moneda" options={OPTIONS} value="ars" onChange={vi.fn()} />,
    );

    await expectNoA11yViolations(container);
  });
});
