import { ProgressBar } from "react-aria-components";

import { cx } from "./cx";
import styles from "./ProgressCircle.module.css";

interface ProgressCircleProps {
  /** Qué se está esperando: es el nombre que anuncia el lector de pantalla. */
  label: string;
}

/**
 * Indicador de progreso circular indeterminado (Material 3): algo está pasando
 * y no se sabe cuánto falta. Sobre el ProgressBar de React Aria, que le da el
 * rol `progressbar` sin valor, como pide WAI-ARIA para una espera indefinida.
 */
export function ProgressCircle({ label }: ProgressCircleProps) {
  return (
    <ProgressBar isIndeterminate aria-label={label} className={cx(styles.root)}>
      <svg className={cx(styles.svg)} viewBox="0 0 48 48" aria-hidden="true">
        <circle className={cx(styles.track)} cx="24" cy="24" r="20" />
        <circle className={cx(styles.indicator)} cx="24" cy="24" r="20" />
      </svg>
    </ProgressBar>
  );
}
