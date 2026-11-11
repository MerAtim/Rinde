import type { ReactNode } from "react";

import { cx } from "../../shared/ui/cx";
import styles from "./Dashboard.module.css";

/**
 * Una tabla que puede ser más ancha que la pantalla y se desplaza dentro de su
 * tarjeta. Sin foco, quien usa teclado no podría desplazarla: no tiene nada
 * enfocable adentro (WCAG 2.1.1). Por eso el contenedor entra en el orden de
 * tabulación con un nombre propio.
 */
export function TableScroll({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={cx(styles.tableScroll)} role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}
