import type { ReactNode } from "react";
import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";

import styles from "./Button.module.css";
import { cx } from "./cx";
import { Icon, type IconName } from "./Icon";

export type ButtonVariant = "filled" | "tonal" | "outlined" | "text";

export interface ButtonProps extends Omit<AriaButtonProps, "className" | "style" | "children"> {
  variant?: ButtonVariant;
  icon?: IconName;
  children: ReactNode;
}

/**
 * Botón de Material 3 sobre React Aria: teclado, foco y lectores de pantalla resueltos.
 * Una sola variante "filled" por pantalla: la acción que el usuario vino a hacer.
 */
export function Button({ variant = "filled", icon, children, ...props }: ButtonProps) {
  return (
    <AriaButton
      {...props}
      className={cx("state-layer", styles.button, styles[variant], icon && styles.withIcon)}
    >
      {icon ? <Icon name={icon} size={18} /> : null}
      {children}
    </AriaButton>
  );
}
