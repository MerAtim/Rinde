import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { PasswordField } from "../../shared/ui/PasswordField";
import { TextField } from "../../shared/ui/TextField";
import { type AuthErrorCode, login } from "./api";
import styles from "./AuthForm.module.css";
import { AuthLayout } from "./AuthLayout";
import { errorCodeOf, fieldOf } from "./errors";
import { SESSION_QUERY_KEY } from "./useSession";

export function LoginPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<AuthErrorCode | null>(null);

  const signIn = useMutation({
    mutationFn: () => login(username, password),
    // Al confirmarse la sesión, la ruta de ingreso redirige sola al inicio.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SESSION_QUERY_KEY }),
  });

  const code = localError ?? errorCodeOf(signIn.error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`auth.errors.${code}`) : "";

  function clearErrors() {
    setLocalError(null);
    signIn.reset();
  }

  return (
    <AuthLayout>
      <section className={cx(styles.card)} aria-labelledby="login-title">
        <div className={cx(styles.heading)}>
          <h1 id="login-title" className={cx(styles.title)}>
            {t("auth.login.title")}
          </h1>
          <p className={cx(styles.subtitle)}>{t("auth.login.subtitle")}</p>
        </div>
        {field === "form" ? <Alert>{message}</Alert> : null}
        <form
          className={cx(styles.form)}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            let error: AuthErrorCode | null = null;
            if (!username.trim()) {
              error = "USERNAME_REQUIRED";
            } else if (!password) {
              error = "PASSWORD_REQUIRED";
            }
            setLocalError(error);
            if (!error) {
              signIn.mutate();
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
          <PasswordField
            label={t("auth.fields.password")}
            value={password}
            onChange={(value) => {
              setPassword(value);
              clearErrors();
            }}
            autoComplete="current-password"
            isRequired
            validationBehavior="aria"
            {...(field === "password" ? { errorMessage: message } : {})}
          />
          <div className={cx(styles.submit)}>
            <Button type="submit" isDisabled={signIn.isPending}>
              {signIn.isPending ? t("auth.login.submitting") : t("auth.login.submit")}
            </Button>
          </div>
        </form>
        <div className={cx(styles.heading)}>
          <p className={cx(styles.footer)}>
            {t("auth.login.forgot")}
            <Link to="/recover" className={cx(styles.link)}>
              {t("auth.login.goRecover")}
            </Link>
          </p>
          <p className={cx(styles.footer)}>
            {t("auth.login.noAccount")}
            <Link to="/signup" className={cx(styles.link)}>
              {t("auth.login.goSignup")}
            </Link>
          </p>
        </div>
      </section>
    </AuthLayout>
  );
}
