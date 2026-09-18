import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { MoneyAmount } from "./MoneyAmount";

describe("MoneyAmount", () => {
  it("un gasto lleva signo, flecha y color, no solo color", () => {
    const { container } = render(<MoneyAmount amount="15300.50" currency="ARS" tone="expense" />);

    expect(screen.getByText("Gasto")).toHaveClass("visually-hidden");
    expect(container.textContent).toContain("15.300,50");
    // El signo menos y la flecha viajan aparte del color (WCAG 1.4.1).
    expect(container.textContent).toContain("\u2212");
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("un ingreso se distingue de un gasto sin mirar el color", () => {
    render(
      <>
        <MoneyAmount amount="1000.00" currency="ARS" tone="income" />
        <MoneyAmount amount="1000.00" currency="ARS" tone="expense" />
      </>,
    );

    expect(screen.getByText("Ingreso").parentElement).toHaveTextContent("+");
    expect(screen.getByText("Gasto").parentElement).toHaveTextContent("\u2212");
  });

  it("un saldo no lleva signo inventado", () => {
    render(<MoneyAmount amount="-2500.00" currency="ARS" />);

    expect(screen.getByText(/2.500,00/)).toBeInTheDocument();
    expect(screen.queryByText("Gasto")).not.toBeInTheDocument();
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(<MoneyAmount amount="1000.00" currency="USD" tone="income" />);

    await expectNoA11yViolations(container);
  });
});
