import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { StatusChip } from "../../shared/ui/StatusChip";
import styles from "./SessionScreen.module.css";

// Render Free duerme la API tras 15 minutos: si tarda, se explica en vez de parecer colgada.
const SLOW_AFTER_MS = 2000;

interface SessionScreenProps {
  state: "loading" | "error";
  onRetry?: () => void;
}

export function SessionScreen({ state, onRetry }: SessionScreenProps) {
  const { t } = useTranslation();
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (state !== "loading") {
      return;
    }
    const timer = setTimeout(() => {
      setSlow(true);
    }, SLOW_AFTER_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [state]);

  return (
    <main className={cx(styles.screen)}>
      <div className={cx(styles.panel)} role="status" aria-live="polite">
        {state === "loading" ? (
          <>
            <StatusChip tone="neutral" icon="schedule" label={t("auth.session.loading")} />
            {slow ? <p className={cx(styles.hint)}>{t("auth.session.waking")}</p> : null}
          </>
        ) : (
          <>
            <StatusChip tone="error" icon="error" label={t("auth.session.error")} />
            {onRetry ? (
              <Button variant="tonal" onPress={onRetry}>
                {t("auth.session.retry")}
              </Button>
            ) : null}
          </>
        )}
      </div>
    </main>
  );
}
