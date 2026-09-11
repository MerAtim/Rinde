import type { ReactNode } from "react";
import { ToggleButton, ToggleButtonGroup } from "react-aria-components";

import { cx } from "./cx";
import { Icon } from "./Icon";
import styles from "./SegmentedButton.module.css";

export interface SegmentOption<T extends string> {
  id: T;
  label: ReactNode;
  /** Nombre completo para lectores de pantalla cuando la etiqueta visible es corta. */
  accessibleLabel?: string;
}

interface SegmentedButtonProps<T extends string> {
  label: string;
  options: readonly SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** Botón segmentado de selección única. El check confirma la elección sin depender del color. */
export function SegmentedButton<T extends string>({
  label,
  options,
  value,
  onChange,
}: SegmentedButtonProps<T>) {
  return (
    <ToggleButtonGroup
      aria-label={label}
      selectionMode="single"
      disallowEmptySelection
      selectedKeys={[value]}
      onSelectionChange={(keys) => {
        const selected = options.find((option) => keys.has(option.id));
        if (selected && selected.id !== value) {
          onChange(selected.id);
        }
      }}
      className={cx(styles.group)}
    >
      {options.map((option) => (
        <ToggleButton
          key={option.id}
          id={option.id}
          {...(option.accessibleLabel ? { "aria-label": option.accessibleLabel } : {})}
          className={cx("state-layer", styles.segment)}
        >
          {({ isSelected }) => (
            <>
              {isSelected ? <Icon name="check" size={18} /> : null}
              <span>{option.label}</span>
            </>
          )}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}
