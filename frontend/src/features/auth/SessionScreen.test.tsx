import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { SessionScreen } from "./SessionScreen";

describe("SessionScreen", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("mientras carga muestra el indicador y, si tarda, explica que el servidor despierta", () => {
    vi.useFakeTimers();
    render(<SessionScreen state="loading" />);

    expect(screen.getByRole("progressbar", { name: "Cargando" })).toBeInTheDocument();
    expect(screen.queryByText(/Despertando el servidor/)).not.toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByText(/Despertando el servidor/)).toBeInTheDocument();
  });

  it("con error ofrece reintentar", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<SessionScreen state="error" onRetry={onRetry} />);

    expect(screen.getByText("Sin conexión con Rinde")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("no tiene problemas de accesibilidad en ningún estado", async () => {
    const { container, rerender } = render(<SessionScreen state="loading" />);
    await expectNoA11yViolations(container);

    rerender(<SessionScreen state="error" onRetry={() => undefined} />);
    await expectNoA11yViolations(container);
  });
});
