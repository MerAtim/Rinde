import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { ProgressCircle } from "./ProgressCircle";

describe("ProgressCircle", () => {
  it("anuncia una espera sin valor, con el nombre que recibe", () => {
    render(<ProgressCircle label="Cargando" />);

    const progress = screen.getByRole("progressbar", { name: "Cargando" });
    expect(progress).not.toHaveAttribute("aria-valuenow");
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(<ProgressCircle label="Cargando" />);

    await expectNoA11yViolations(container);
  });
});
