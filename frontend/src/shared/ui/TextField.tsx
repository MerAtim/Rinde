import {
  TextField as AriaTextField,
  type TextFieldProps as AriaTextFieldProps,
  FieldError,
  Input,
  Label,
  Text,
} from "react-aria-components";

import { cx } from "./cx";
import { Icon } from "./Icon";
import styles from "./TextField.module.css";

export interface TextFieldProps extends Omit<
  AriaTextFieldProps,
  "className" | "style" | "children"
> {
  label: string;
  description?: string;
  /** Dice qué pasó y cómo corregirlo, nunca solo "inválido". */
  errorMessage?: string;
  /** Se muestra cuando la etiqueta flota; por ejemplo "$". */
  prefix?: string;
}

/** Campo con borde y etiqueta flotante de Material 3. */
export function TextField({
  label,
  description,
  errorMessage,
  prefix,
  isInvalid,
  ...props
}: TextFieldProps) {
  const invalid = Boolean(errorMessage) || Boolean(isInvalid);

  return (
    <AriaTextField {...props} isInvalid={invalid} className={cx(styles.field)}>
      <div className={cx(styles.box)}>
        {prefix ? (
          <span className={cx(styles.prefix)} aria-hidden="true">
            {prefix}
          </span>
        ) : null}
        <Input className={cx(styles.input)} placeholder=" " />
        <Label className={cx(styles.label)}>{label}</Label>
      </div>
      {description && !invalid ? (
        <Text slot="description" className={cx(styles.helper)}>
          {description}
        </Text>
      ) : null}
      <FieldError className={cx(styles.helper, styles.error)}>
        <Icon name="error" size={16} />
        {errorMessage}
      </FieldError>
    </AriaTextField>
  );
}
