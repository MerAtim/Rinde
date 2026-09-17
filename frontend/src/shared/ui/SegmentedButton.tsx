import { type ReactNode, useId } from "react";
import { ToggleButton, ToggleButtonGroup } from "react-aria-components";

import { cx } from "./cx";
import { Icon } from "./Icon";
import styles from "./SegmentedButton.module.css";

export interface SegmentOption<T extends string> {
  id: T;
  label: ReactNode;
  /** Nombre completo para lectores de pantalla cuando la etiqueta visible es corta. */
  accessibleLabel?: string;
  /** Una opción que hoy no aplica se muestra deshabilitada, y el porqué va en `description`. */
  isDisabled?: boolean;
}

interface SegmentedButtonProps<T extends string> {
  label: string;
  /**
   * En un formulario la etiqueta se muestra arriba, como en cualquier campo. En
   * una barra (idioma, tema) el contexto alcanza y queda solo para lectores.
   */
  isLabelVisible?: boolean;
  /** Aclaración visible debajo del grupo, asociada para lectores de pantalla. */
  description?: string;
  options: readonly SegmentOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** Botón segmentado de selección única. El check confirma la elección sin depender del color. */
export function SegmentedButton<T extends string>({
  label,
  isLabelVisible = false,
  description,
  options,
  value,
  onChange,
}: SegmentedButtonProps<T>) {
  const labelId = useId();
  const descriptionId = useId();

  const group = (
    <ToggleButtonGroup
      {...(isLabelVisible ? { "aria-labelledby": labelId } : { "aria-label": label })}
      {...(description ? { "aria-describedby": descriptionId } : {})}
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
          isDisabled={option.isDisabled ?? false}
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

  if (!isLabelVisible && !description) {
    return group;
  }
  return (
    <div className={cx(styles.field)}>
      {isLabelVisible ? (
        <span id={labelId} className={cx(styles.label)}>
          {label}
        </span>
      ) : null}
      {group}
      {description ? (
        <p id={descriptionId} className={cx(styles.description)}>
          {description}
        </p>
      ) : null}
    </div>
  );
}
