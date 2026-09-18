import { Label, RadioButton, RadioField, RadioGroup } from "react-aria-components";

import { cx } from "./cx";
import { Icon, type IconName } from "./Icon";
import styles from "./RadioCardGroup.module.css";

export interface RadioCardOption<T extends string> {
  id: T;
  label: string;
  icon: IconName;
}

interface RadioCardGroupProps<T extends string> {
  label: string;
  options: readonly RadioCardOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/**
 * Selección única entre pocas opciones que se reconocen mejor con un ícono,
 * como el tipo de cuenta. Es un grupo de radios: flechas para moverse y el
 * check confirma la elección sin depender del color.
 */
export function RadioCardGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: RadioCardGroupProps<T>) {
  return (
    <RadioGroup
      value={value}
      onChange={(selected) => {
        const option = options.find((candidate) => candidate.id === selected);
        if (option) {
          onChange(option.id);
        }
      }}
      className={cx(styles.group)}
    >
      <Label className={cx(styles.legend)}>{label}</Label>
      <div className={cx(styles.options)}>
        {options.map((option) => (
          <RadioField key={option.id} value={option.id}>
            <RadioButton className={cx("state-layer", styles.card)}>
              {({ isSelected }) => (
                <>
                  <Icon name={option.icon} size={24} />
                  <span className={cx(styles.label)}>{option.label}</span>
                  <span className={cx(styles.check)}>
                    {isSelected ? <Icon name="check" size={18} /> : null}
                  </span>
                </>
              )}
            </RadioButton>
          </RadioField>
        ))}
      </div>
    </RadioGroup>
  );
}
