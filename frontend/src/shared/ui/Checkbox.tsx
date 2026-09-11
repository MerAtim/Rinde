import type { ReactNode } from "react";
import { CheckboxButton, CheckboxField, type CheckboxFieldProps } from "react-aria-components";

import styles from "./Checkbox.module.css";
import { cx } from "./cx";
import { Icon } from "./Icon";

interface CheckboxProps extends Omit<CheckboxFieldProps, "className" | "style" | "children"> {
  children: ReactNode;
}

/** Casilla de Material 3: el check confirma la elección sin depender del color. */
export function Checkbox({ children, ...props }: CheckboxProps) {
  return (
    <CheckboxField {...props}>
      <CheckboxButton className={cx(styles.checkbox)}>
        {({ isSelected }) => (
          <>
            <span className={cx("state-layer", styles.box)}>
              {isSelected ? <Icon name="check" size={18} /> : null}
            </span>
            <span>{children}</span>
          </>
        )}
      </CheckboxButton>
    </CheckboxField>
  );
}
