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
  /**
   * Un número chico sobre el ícono, como el de Material 3. Es solo visual: la
   * etiqueta tiene que decir lo mismo con palabras ("Alertas, 2 sin leer").
   * Con un string vacío no se ve, pero el marcado no cambia cuando aparece.
   */
  badge?: string;
}

/** Se ve como un botón de ícono pero lleva a otra pantalla: es un enlace, y así se anuncia. */
export function LinkIconButton({ icon, label, badge, ...props }: LinkIconButtonProps) {
  const link = (
    <Link {...props} aria-label={label} className={cx("state-layer", styles.iconButton)}>
      <Icon name={icon} size={24} />
    </Link>
  );
  if (badge === undefined) {
    return link;
  }
  // Fuera del enlace: la capa de estado recorta lo que sale de su círculo.
  return (
    <span className={cx(styles.withBadge)}>
      {link}
      {badge ? (
        <span className={cx(styles.badge)} aria-hidden="true">
          {badge}
        </span>
      ) : null}
    </span>
  );
}
