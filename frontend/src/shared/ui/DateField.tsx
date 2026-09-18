import { useId } from "react";

import { cx } from "./cx";
import { Icon } from "./Icon";
import styles from "./DateField.module.css";

interface DateFieldProps {
  label: string;
  /** Fecha en formato ISO (aaaa-mm-dd), como la guarda el servidor. */
  value: string;
  onChange: (value: string) => void;
  /** La última fecha admitida, también en ISO. */
  max?: string;
  description?: string;
  errorMessage?: string;
}

/**
 * Campo de fecha nativo. Se prefiere al selector propio de React Aria porque el
 * teclado del celular y el calendario del sistema ya resuelven el caso, en el
 * idioma y el formato que la persona configuró, sin sumar peso al paquete.
 */
export function DateField({
  label,
  value,
  onChange,
  max,
  description,
  errorMessage,
}: DateFieldProps) {
  const inputId = useId();
  const helperId = useId();
  const invalid = Boolean(errorMessage);

  return (
    <div className={cx(styles.field)} data-invalid={invalid || undefined}>
      <label htmlFor={inputId} className={cx(styles.label)}>
        {label}
      </label>
      <input
        id={inputId}
        type="date"
        className={cx(styles.input)}
        value={value}
        max={max}
        aria-describedby={description || errorMessage ? helperId : undefined}
        aria-invalid={invalid || undefined}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
      {description || errorMessage ? (
        <p id={helperId} className={cx(styles.helper, invalid && styles.error)}>
          {invalid ? <Icon name="error" size={16} /> : null}
          {errorMessage ?? description}
        </p>
      ) : null}
    </div>
  );
}
