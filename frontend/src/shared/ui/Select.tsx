import {
  Button as AriaButton,
  Select as AriaSelect,
  FieldError,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  SelectValue,
  Text,
} from "react-aria-components";

import { cx } from "./cx";
import { Icon } from "./Icon";
import styles from "./Select.module.css";

export interface SelectOption {
  id: string;
  label: string;
  /** Agrupa visualmente; por ejemplo, gastos e ingresos. */
  group?: string;
}

interface SelectProps {
  label: string;
  placeholder: string;
  options: readonly SelectOption[];
  value: string | null;
  onChange: (value: string) => void;
  description?: string;
  errorMessage?: string;
  isDisabled?: boolean;
}

/** Lista desplegable de Material 3 sobre React Aria: teclado y foco resueltos. */
export function Select({
  label,
  placeholder,
  options,
  value,
  onChange,
  description,
  errorMessage,
  isDisabled = false,
}: SelectProps) {
  return (
    <AriaSelect
      className={cx(styles.field)}
      value={value}
      isDisabled={isDisabled}
      isInvalid={Boolean(errorMessage)}
      validationBehavior="aria"
      onChange={(key) => {
        onChange(String(key));
      }}
    >
      <Label className={cx(styles.label)}>{label}</Label>
      <AriaButton className={cx("state-layer", styles.trigger)}>
        <SelectValue className={cx(styles.value)}>
          {({ isPlaceholder, selectedText }) => (
            <span className={cx(isPlaceholder && styles.placeholder)}>
              {isPlaceholder ? placeholder : selectedText}
            </span>
          )}
        </SelectValue>
        <Icon name="chevron-right" size={20} />
      </AriaButton>
      {description && !errorMessage ? (
        <Text slot="description" className={cx(styles.helper)}>
          {description}
        </Text>
      ) : null}
      <FieldError className={cx(styles.helper, styles.error)}>
        <Icon name="error" size={16} />
        {errorMessage}
      </FieldError>
      <Popover className={cx(styles.popover)}>
        <ListBox className={cx(styles.list)} items={options}>
          {(option: SelectOption) => (
            <ListBoxItem
              id={option.id}
              textValue={option.label}
              className={cx("state-layer", styles.option)}
            >
              {({ isSelected }) => (
                <>
                  <span>{option.label}</span>
                  {isSelected ? <Icon name="check" size={18} /> : null}
                </>
              )}
            </ListBoxItem>
          )}
        </ListBox>
      </Popover>
    </AriaSelect>
  );
}
