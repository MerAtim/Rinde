import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { PasswordField } from "../../shared/ui/PasswordField";
import { TextField } from "../../shared/ui/TextField";
import { type AuthErrorCode, recover } from "./api";
import styles from "./AuthForm.module.css";
import { AuthLayout } from "./AuthLayout";
import {
  errorCodeOf,
  fieldOf,
  MIN_PASSWORD_LENGTH,
  passwordLength,
  validateNewPassword,
} from "./errors";
import type { RecoveryCodeState } from "./RecoveryCodePage";

export function RecoverPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<AuthErrorCode | null>(null);

  const recovery = useMutation({
    mutationFn: () => recover(username, recoveryCode, password),
    onSuccess: (result) => {
      const state: RecoveryCodeState = {
        recoveryCode: result.recovery_code,
        username: username.trim().toLowerCase(),
        reason: "recover",
      };
      void navigate("/recovery-code", { state });
    },
  });

  const code = localError ?? errorCodeOf(recovery.error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`auth.errors.${code}`) : "";

  function clearErrors() {
    setLocalError(null);
    recovery.reset();
  }

  return (
    <AuthLayout>
      <section className={cx(styles.card)} aria-labelledby="recover-title">
        <div className={cx(styles.heading)}>
          <h1 id="recover-title" className={cx(styles.title)}>
            {t("auth.recover.title")}
          </h1>
          <p className={cx(styles.subtitle)}>{t("auth.recover.subtitle")}</p>
        </div>
        {field === "form" ? <Alert>{message}</Alert> : null}
        <form
          className={cx(styles.form)}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            let error: AuthErrorCode | null;
            if (!username.trim()) {
              error = "USERNAME_REQUIRED";
            } else if (!recoveryCode.trim()) {
              error = "RECOVERY_CODE_REQUIRED";
            } else {
              error = validateNewPassword(password);
            }
            setLocalError(error);
            if (!error) {
              recovery.mutate();
            }
          }}
        >
          <TextField
            label={t("auth.fields.username")}
            value={username}
            onChange={(value) => {
              setUsername(value);
              clearErrors();
            }}
            autoComplete="username"
            isRequired
            validationBehavior="aria"
            {...(field === "username" ? { errorMessage: message } : {})}
          />
          <TextField
            label={t("auth.fields.recoveryCode")}
            value={recoveryCode}
            onChange={(value) => {
              setRecoveryCode(value);
              clearErrors();
            }}
            autoComplete="off"
            spellCheck="false"
            isRequired
            validationBehavior="aria"
            description={t("auth.fields.recoveryCodeHelp")}
            {...(field === "recoveryCode" ? { errorMessage: message } : {})}
          />
          <PasswordField
            label={t("auth.fields.newPassword")}
            value={password}
            onChange={(value) => {
              setPassword(value);
              clearErrors();
            }}
            autoComplete="new-password"
            isRequired
            validationBehavior="aria"
            description={t("auth.fields.passwordHelp", {
              length: passwordLength(password),
              min: MIN_PASSWORD_LENGTH,
            })}
            {...(field === "password" ? { errorMessage: message } : {})}
          />
          <div className={cx(styles.submit)}>
            <Button type="submit" isDisabled={recovery.isPending}>
              {recovery.isPending ? t("auth.recover.submitting") : t("auth.recover.submit")}
            </Button>
          </div>
        </form>
        <p className={cx(styles.footer)}>
          <Link to="/login" className={cx(styles.link)}>
            {t("auth.recover.back")}
          </Link>
        </p>
      </section>
    </AuthLayout>
  );
}
