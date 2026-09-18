import { useEffect } from "react";
import { Button as AriaButton } from "react-aria-components";
import { useTranslation } from "react-i18next";

import { cx } from "./cx";
import { Icon } from "./Icon";
import styles from "./Snackbar.module.css";

// Seis segundos: lo que recomienda Material 3 para un aviso con acción.
const VISIBLE_MS = 6000;

interface SnackbarProps {
  message: string;
  onDismiss: () => void;
  action?: { label: string; onPress: () => void };
}

/**
 * Aviso breve con una acción, para deshacer en lugar de preguntar antes
 * (docs/design-system.md). Se anuncia solo y se va a los seis segundos.
 */
export function Snackbar({ message, onDismiss, action }: SnackbarProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, VISIBLE_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [onDismiss, message]);

  const { t } = useTranslation();

  return (
    <div role="status" className={cx(styles.snackbar)}>
      <p className={cx(styles.message)}>{message}</p>
      <div className={cx(styles.actions)}>
        {action ? (
          <AriaButton className={cx(styles.action)} onPress={action.onPress}>
            <Icon name="undo" size={18} />
            {action.label}
          </AriaButton>
        ) : null}
        <AriaButton
          className={cx(styles.close)}
          aria-label={t("common.dismiss")}
          onPress={onDismiss}
        >
          <Icon name="close" size={18} />
        </AriaButton>
      </div>
    </div>
  );
}
