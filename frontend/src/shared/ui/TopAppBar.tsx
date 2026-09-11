import type { ReactNode } from "react";

import { cx } from "./cx";
import styles from "./TopAppBar.module.css";

interface TopAppBarProps {
  start: ReactNode;
  end?: ReactNode;
}

/** Barra superior fija y translúcida: el contenido pasa por debajo sin perder contexto. */
export function TopAppBar({ start, end }: TopAppBarProps) {
  return (
    <header className={cx(styles.bar)}>
      <div className={cx(styles.start)}>{start}</div>
      {end ? <div className={cx(styles.end)}>{end}</div> : null}
    </header>
  );
}
