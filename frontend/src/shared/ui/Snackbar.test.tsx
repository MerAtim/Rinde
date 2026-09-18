import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { Snackbar } from "./Snackbar";

afterEach(() => {
  vi.useRealTimers();
});

describe("Snackbar", () => {
  it("se anuncia y ofrece deshacer", async () => {
    const user = userEvent.setup();
    const onPress = vi.fn();
    render(
      <Snackbar
        message="Borraste el movimiento"
        onDismiss={vi.fn()}
        action={{ label: "Deshacer", onPress }}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Borraste el movimiento");
    await user.click(screen.getByRole("button", { name: "Deshacer" }));

    expect(onPress).toHaveBeenCalledOnce();
  });

  it("se va solo a los seis segundos", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    render(<Snackbar message="Listo" onDismiss={onDismiss} />);

    vi.advanceTimersByTime(5999);
    expect(onDismiss).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);

    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("se puede cerrar a mano", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(<Snackbar message="Listo" onDismiss={onDismiss} />);

    await user.click(screen.getByRole("button", { name: "Cerrar el aviso" }));

    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(
      <Snackbar
        message="Borraste el movimiento"
        onDismiss={vi.fn()}
        action={{ label: "Deshacer", onPress: vi.fn() }}
      />,
    );

    await expectNoA11yViolations(container);
  });
});
