import type { ReactNode } from "react";
import { Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";

import { Button } from "./Button";
import styles from "./ConfirmDialog.module.css";
import { cx } from "./cx";

interface ConfirmDialogProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  /** Qué cambia y qué no se puede deshacer, dicho sin rodeos. */
  children: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  isPending?: boolean;
}

/**
 * Diálogo de confirmación, solo para acciones irreversibles (docs/design-system.md):
 * confirmar todo entrena a tocar "Sí" sin leer. React Aria atrapa el foco, lo
 * devuelve al cerrar y cierra con Esc.
 */
export function ConfirmDialog({
  isOpen,
  onOpenChange,
  title,
  children,
  confirmLabel,
  cancelLabel,
  onConfirm,
  isPending = false,
}: ConfirmDialogProps) {
  return (
    <ModalOverlay
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isDismissable={!isPending}
      isKeyboardDismissDisabled={isPending}
      className={cx(styles.overlay)}
    >
      <Modal className={cx(styles.modal)}>
        <Dialog role="alertdialog" className={cx(styles.dialog)}>
          {({ close }) => (
            <>
              <Heading slot="title" className={cx(styles.title)}>
                {title}
              </Heading>
              <div className={cx(styles.body)}>{children}</div>
              <div className={cx(styles.actions)}>
                <Button variant="text" onPress={close} isDisabled={isPending}>
                  {cancelLabel}
                </Button>
                <Button onPress={onConfirm} isDisabled={isPending}>
                  {confirmLabel}
                </Button>
              </div>
            </>
          )}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}
