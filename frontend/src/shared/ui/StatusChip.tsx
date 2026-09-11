import { cx } from "./cx";
import { Icon, type IconName } from "./Icon";
import styles from "./StatusChip.module.css";

export type StatusTone = "ok" | "warning" | "error" | "neutral";

interface StatusChipProps {
  tone: StatusTone;
  icon: IconName;
  label: string;
}

/** Estado con ícono y texto: el color refuerza, nunca informa solo. */
export function StatusChip({ tone, icon, label }: StatusChipProps) {
  return (
    <span className={cx(styles.chip)} data-tone={tone}>
      <Icon name={icon} size={16} />
      {label}
    </span>
  );
}
