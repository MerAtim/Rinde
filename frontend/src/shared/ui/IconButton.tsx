import { Button as AriaButton, type ButtonProps as AriaButtonProps } from "react-aria-components";

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
