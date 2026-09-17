import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { RadioCardGroup } from "../../shared/ui/RadioCardGroup";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import { TextField } from "../../shared/ui/TextField";
import styles from "./Accounts.module.css";
import {
  ACCOUNT_KINDS,
  ACCOUNT_NAME_MAX_LENGTH,
  type AccountErrorCode,
  type AccountKind,
  CURRENCIES,
  type Currency,
  isCurrencyAllowed,
} from "./api";
import { errorCodeOf, fieldOf, nameLength, validateNewAccount } from "./errors";
import { KIND_ICON } from "./presentation";
import { useOpenAccount } from "./useAccounts";

export function NewAccountPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<AccountKind>("cash");
  // Pesos por omisión: es la moneda más probable para quien usa Rinde en Argentina.
  const [currency, setCurrency] = useState<Currency>("ARS");
  const [localError, setLocalError] = useState<AccountErrorCode | null>(null);

  const open = useOpenAccount();

  const code = localError ?? errorCodeOf(open.error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`accounts.errors.${code}`) : "";

  function clearErrors() {
    setLocalError(null);
    open.reset();
  }

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/accounts" variant="text" icon="arrow-back">
          {t("accounts.new.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("accounts.new.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("accounts.new.subtitle")}</p>
      </div>
      {field === "form" ? <Alert>{message}</Alert> : null}
      <form
        className={cx(styles.form)}
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          const error = validateNewAccount(name, kind, currency);
          setLocalError(error);
          if (error) {
            return;
          }
          open.mutate(
            { name, kind, currency },
            {
              onSuccess: (account) => {
                void navigate("/accounts", {
                  state: withAnnouncement(t("accounts.list.opened", { name: account.name })),
                });
              },
            },
          );
        }}
      >
        <TextField
          label={t("accounts.fields.name")}
          description={t("accounts.fields.nameHelp", {
            length: nameLength(name),
            max: ACCOUNT_NAME_MAX_LENGTH,
          })}
          value={name}
          onChange={(value) => {
            setName(value);
            clearErrors();
          }}
          autoComplete="off"
          isRequired
          validationBehavior="aria"
          {...(field === "name" ? { errorMessage: message } : {})}
        />
        <RadioCardGroup
          label={t("accounts.fields.kind")}
          options={ACCOUNT_KINDS.map((id) => ({
            id,
            label: t(`accounts.kind.${id}`),
            icon: KIND_ICON[id],
          }))}
          value={kind}
          onChange={(value) => {
            setKind(value);
            // Bitcoin deja de ser válido fuera de una billetera cripto: la
            // opción queda deshabilitada y la ayuda debajo explica por qué.
            if (!isCurrencyAllowed(value, currency)) {
              setCurrency("ARS");
            }
            clearErrors();
          }}
        />
        <SegmentedButton
          label={t("accounts.fields.currency")}
          isLabelVisible
          description={t("accounts.fields.currencyHelp")}
          options={CURRENCIES.map((id) => ({
            id,
            label: id,
            accessibleLabel: t(`accounts.currency.${id}`),
            isDisabled: !isCurrencyAllowed(kind, id),
          }))}
          value={currency}
          onChange={(value) => {
            setCurrency(value);
            clearErrors();
          }}
        />
        <div className={cx(styles.actions)}>
          <Button type="submit" isDisabled={open.isPending}>
            {open.isPending ? t("accounts.new.submitting") : t("accounts.new.submit")}
          </Button>
        </div>
      </form>
    </div>
  );
}
