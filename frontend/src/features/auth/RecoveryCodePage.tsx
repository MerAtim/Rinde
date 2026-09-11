import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useLocation, useNavigate } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { Checkbox } from "../../shared/ui/Checkbox";
import { cx } from "../../shared/ui/cx";
import styles from "./RecoveryCodePage.module.css";
import { useSetSession } from "./useSession";

export interface RecoveryCodeState {
  recoveryCode: string;
  username: string;
  reason: "signup" | "recover";
}

function isRecoveryCodeState(value: unknown): value is RecoveryCodeState {
  return (
    typeof value === "object" &&
    value !== null &&
    "recoveryCode" in value &&
    typeof value.recoveryCode === "string" &&
    "username" in value &&
    typeof value.username === "string" &&
    "reason" in value &&
    (value.reason === "signup" || value.reason === "recover")
  );
}

function downloadText(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * El código se muestra una sola vez: no se sigue hasta confirmar que se guardó.
 * Vive fuera de las rutas protegidas para que ninguna redirección lo haga desaparecer.
 */
export function RecoveryCodePage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const setSession = useSetSession();
  const [saved, setSaved] = useState(false);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const state: unknown = location.state;

  if (!isRecoveryCodeState(state)) {
    return <Navigate to="/" replace />;
  }
  const { recoveryCode, username, reason } = state;

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(recoveryCode);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  }

  return (
    <main className={cx(styles.screen)}>
      <section className={cx(styles.card)} aria-labelledby="code-title">
        <div className={cx(styles.heading)}>
          <h1 id="code-title" className={cx(styles.title)}>
            {reason === "signup" ? t("auth.code.titleNew") : t("auth.code.titleRotated")}
          </h1>
          <p className={cx(styles.explain)}>{t("auth.code.explain")}</p>
          {reason === "recover" ? (
            <p className={cx(styles.explain)}>{t("auth.code.rotatedNote")}</p>
          ) : null}
        </div>
        <p className={cx(styles.code)} aria-label={t("auth.code.label")}>
          {recoveryCode}
        </p>
        <div className={cx(styles.actions)}>
          <Button
            variant="tonal"
            icon="content-copy"
            onPress={() => {
              void copyCode();
            }}
          >
            {copy === "copied" ? t("auth.code.copied") : t("auth.code.copy")}
          </Button>
          <Button
            variant="outlined"
            icon="download"
            onPress={() => {
              downloadText(
                t("auth.code.fileName"),
                t("auth.code.fileText", { username, code: recoveryCode }),
              );
            }}
          >
            {t("auth.code.download")}
          </Button>
        </div>
        {copy === "failed" ? <Alert>{t("auth.code.copyFailed")}</Alert> : null}
        <Checkbox isSelected={saved} onChange={setSaved}>
          {t("auth.code.confirm")}
        </Checkbox>
        <div className={cx(styles.continue)}>
          <Button
            isDisabled={!saved}
            onPress={() => {
              setSession({ username });
              void navigate("/", { replace: true });
            }}
          >
            {t("auth.code.continue")}
          </Button>
        </div>
      </section>
    </main>
  );
}
