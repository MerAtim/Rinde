import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { PasswordField } from "../../shared/ui/PasswordField";
import { TextField } from "../../shared/ui/TextField";
import { type AuthErrorCode, register } from "./api";
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

export function SignupPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<AuthErrorCode | null>(null);

  const signup = useMutation({
    mutationFn: () => register(username, password),
    onSuccess: (result) => {
      // La sesión se marca recién al salir de la pantalla del código: primero hay que guardarlo.
      const state: RecoveryCodeState = {
        recoveryCode: result.recovery_code,
        username: result.username,
        reason: "signup",
      };
      void navigate("/recovery-code", { state });
    },
  });

  const code = localError ?? errorCodeOf(signup.error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`auth.errors.${code}`) : "";

  return (
    <AuthLayout>
      <section className={cx(styles.card)} aria-labelledby="signup-title">
        <div className={cx(styles.heading)}>
          <h1 id="signup-title" className={cx(styles.title)}>
            {t("auth.signup.title")}
          </h1>
          <p className={cx(styles.subtitle)}>{t("auth.signup.subtitle")}</p>
        </div>
        {field === "form" ? <Alert>{message}</Alert> : null}
        <form
          className={cx(styles.form)}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            const error = username.trim() ? validateNewPassword(password) : "USERNAME_REQUIRED";
            setLocalError(error);
            if (!error) {
              signup.mutate();
            }
          }}
        >
          <TextField
            label={t("auth.fields.username")}
            value={username}
            onChange={(value) => {
              setUsername(value);
              setLocalError(null);
              signup.reset();
            }}
            autoComplete="username"
            isRequired
            validationBehavior="aria"
            description={t("auth.fields.usernameHelp")}
            {...(field === "username" ? { errorMessage: message } : {})}
          />
          <PasswordField
            label={t("auth.fields.password")}
            value={password}
            onChange={(value) => {
              setPassword(value);
              setLocalError(null);
              signup.reset();
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
            <Button type="submit" isDisabled={signup.isPending}>
              {signup.isPending ? t("auth.signup.submitting") : t("auth.signup.submit")}
            </Button>
          </div>
        </form>
        <p className={cx(styles.footer)}>
          {t("auth.signup.haveAccount")}
          <Link to="/login" className={cx(styles.link)}>
            {t("auth.signup.goLogin")}
          </Link>
        </p>
      </section>
    </AuthLayout>
  );
}
