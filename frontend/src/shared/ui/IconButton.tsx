import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";
import { Link, type LinkProps } from "react-router";

import { cx } from "./cx";
import { Icon, type IconName } from "./Icon";
import styles from "./IconButton.module.css";

export interface IconButtonProps extends Omit<
  AriaButtonProps,
  "className" | "style" | "children" | "aria-label"
> {
  icon: IconName;
  /** Obligatoria: un ícono solo no se lee en voz alta. */
  label: string;
}

export function IconButton({ icon, label, ...props }: IconButtonProps) {
  return (
    <AriaButton {...props} aria-label={label} className={cx("state-layer", styles.iconButton)}>
      <Icon name={icon} size={24} />
    </AriaButton>
  );
}

export interface LinkIconButtonProps extends Omit<
  LinkProps,
  "className" | "style" | "children" | "aria-label"
> {
  icon: IconName;
  /** Obligatoria: un ícono solo no se lee en voz alta. */
  label: string;
}

/** Se ve como un botón de ícono pero lleva a otra pantalla: es un enlace, y así se anuncia. */
export function LinkIconButton({ icon, label, ...props }: LinkIconButtonProps) {
  return (
    <Link {...props} aria-label={label} className={cx("state-layer", styles.iconButton)}>
      <Icon name={icon} size={24} />
    </Link>
  );
}
