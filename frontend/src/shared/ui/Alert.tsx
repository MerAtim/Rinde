import type { ReactNode } from "react";

import styles from "./Alert.module.css";
import { cx } from "./cx";
import { Icon } from "./Icon";

/** Aviso de error que se anuncia al aparecer. Dice qué pasó y cómo seguir. */
export function Alert({ children }: { children: ReactNode }) {
  return (
    <div role="alert" className={cx(styles.alert)}>
      <Icon name="error" size={20} />
      <p>{children}</p>
    </div>
  );
}
