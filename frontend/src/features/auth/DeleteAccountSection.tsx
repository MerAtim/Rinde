import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { cx } from "../../shared/ui/cx";
import { PasswordField } from "../../shared/ui/PasswordField";
import { type AuthErrorCode, deleteAccount } from "./api";
import styles from "./DeleteAccountSection.module.css";
import { errorCodeOf } from "./errors";
import { useSession, useSetSession } from "./useSession";

/** Lo que la pantalla de ingreso recibe para avisar que la cuenta se borró. */
export interface AccountDeletedState {
  accountDeleted: true;
}

/**
 * Borrar la cuenta propia (Ley 25.326, art. 16; ADR-0034). Es irreversible, así
 * que pide la contraseña en un diálogo que dice qué se pierde. Una demo no se
 * borra a mano: no tiene contraseña y se borra sola (ADR-0028).
 */
export function DeleteAccountSection() {
  const { t } = useTranslation();
  const session = useSession();
  const setSession = useSetSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [isOpen, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<AuthErrorCode | null>(null);

  const remove = useMutation({
    mutationFn: () => deleteAccount(password),
    onSuccess: () => {
      // Nada de la cuenta borrada queda en memoria. Las tres actualizaciones se
      // aplican juntas: la pantalla de ingreso se abre ya sin sesión y con el aviso.
      queryClient.clear();
      setSession(null);
      const state: AccountDeletedState = { accountDeleted: true };
      void navigate("/login", { replace: true, state });
    },
  });

  const isDemo = Boolean(session.data?.demo_expires_at);
  const code = localError ?? errorCodeOf(remove.error);

  function close() {
    setOpen(false);
    setPassword("");
    setLocalError(null);
    remove.reset();
  }

  return (
    <section className={cx(styles.section)} aria-labelledby="delete-account-title">
      <h2 id="delete-account-title" className={cx(styles.title)}>
        {t("account.delete.title")}
      </h2>
      {isDemo ? (
        <p className={cx(styles.text)}>{t("account.delete.demo")}</p>
      ) : (
        <>
          <p className={cx(styles.text)}>{t("account.delete.description")}</p>
          <div>
            <Button
              variant="outlined"
              icon="delete"
              onPress={() => {
                setOpen(true);
              }}
            >
              {t("account.delete.open")}
            </Button>
          </div>
        </>
      )}
      <ConfirmDialog
        isOpen={isOpen}
        onOpenChange={(open) => {
          if (!open) {
            close();
          }
        }}
        title={t("account.delete.confirmTitle")}
        confirmLabel={remove.isPending ? t("account.delete.deleting") : t("account.delete.confirm")}
        cancelLabel={t("account.delete.cancel")}
        isPending={remove.isPending}
        onConfirm={() => {
          if (!password) {
            setLocalError("PASSWORD_REQUIRED");
            return;
          }
          setLocalError(null);
          remove.mutate();
        }}
      >
        <p>{t("account.delete.warning")}</p>
        {code && code !== "PASSWORD_REQUIRED" && code !== "INVALID_CREDENTIALS" ? (
          <Alert>{t(`auth.errors.${code}`)}</Alert>
        ) : null}
        <PasswordField
          label={t("account.delete.password")}
          autoComplete="current-password"
          value={password}
          onChange={(value) => {
            setPassword(value);
            setLocalError(null);
            remove.reset();
          }}
          {...(code === "PASSWORD_REQUIRED" || code === "INVALID_CREDENTIALS"
            ? { errorMessage: t(`account.delete.errors.${code}`) }
            : {})}
          isDisabled={remove.isPending}
        />
      </ConfirmDialog>
    </section>
  );
}
