import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { Button } from "./Button";
import { ConfirmDialog } from "./ConfirmDialog";

function Harness({ onConfirm }: { onConfirm: () => void }) {
  const [isOpen, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="outlined"
        onPress={() => {
          setOpen(true);
        }}
      >
        Archivar
      </Button>
      <ConfirmDialog
        isOpen={isOpen}
        onOpenChange={setOpen}
        title="¿Archivar Galicia?"
        confirmLabel="Archivar cuenta"
        cancelLabel="Cancelar"
        onConfirm={onConfirm}
      >
        <p>No se puede deshacer.</p>
      </ConfirmDialog>
    </>
  );
}

describe("ConfirmDialog", () => {
  it("confirma la acción", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);

    await user.click(screen.getByRole("button", { name: "Archivar" }));
    await user.click(await screen.findByRole("button", { name: "Archivar cuenta" }));

    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("se cierra con Esc sin confirmar y devuelve el foco", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);

    await user.tab();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("alertdialog", { name: "¿Archivar Galicia?" })).toBeVisible();
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Archivar" })).toHaveFocus();
    });
  });

  it("no tiene problemas de accesibilidad", async () => {
    const user = userEvent.setup();
    render(<Harness onConfirm={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Archivar" }));
    await screen.findByRole("alertdialog");

    await expectNoA11yViolations(document.body);
  });
});
