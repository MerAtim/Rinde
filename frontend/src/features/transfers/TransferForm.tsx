import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { DateField } from "../../shared/ui/DateField";
import { Select } from "../../shared/ui/Select";
import { TextField } from "../../shared/ui/TextField";
import type { Account } from "../accounts/api";
import { DESCRIPTION_MAX_LENGTH } from "../transactions/api";
import { toDecimalString, validateAmount } from "../transactions/errors";
import { today } from "../transactions/presentation";
import styles from "../transactions/Transactions.module.css";
import type { TransferErrorCode } from "./api";
import { errorCodeOf, fieldOf } from "./errors";

export interface TransferDraft {
  fromAccountId: string;
  toAccountId: string;
  sent: string;
  received: string;
  occurredOn: string;
  description: string;
}

interface TransferFormProps {
  accounts: Account[];
  draft: TransferDraft;
  submitLabel: string;
  submittingLabel: string;
  isPending: boolean;
  error: unknown;
  onSubmit: (values: { sent: string; received: string; draft: TransferDraft }) => void;
}

export function TransferForm({
  accounts,
  draft: initial,
  submitLabel,
  submittingLabel,
  isPending,
  error,
  onSubmit,
}: TransferFormProps) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(initial);
  const [localError, setLocalError] = useState<TransferErrorCode | null>(null);

  const code = localError ?? errorCodeOf(error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`transfers.errors.${code}`) : "";
  const origin = accounts.find((row) => row.id === draft.fromAccountId);
  const destination = accounts.find((row) => row.id === draft.toAccountId);
  // Entre cuentas de la misma moneda casi siempre entra lo mismo que sale, y
  // pedir el mismo número dos veces molesta. Cuando cambian de moneda no hay
  // forma de saberlo sin preguntarlo: la tasa es la que le dieron a la persona.
  const isSameCurrency = origin !== undefined && origin.currency === destination?.currency;

  function update(changes: Partial<TransferDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
    setLocalError(null);
  }

  function validate(): TransferErrorCode | null {
    if (!draft.fromAccountId || !draft.toAccountId) {
      return "ACCOUNTS_REQUIRED";
    }
    if (draft.fromAccountId === draft.toAccountId) {
      return "TRANSFER_SAME_ACCOUNT";
    }
    const sent = validateAmount(draft.sent);
    if (sent !== null) {
      return sent === "AMOUNT_REQUIRED" ? "SENT_REQUIRED" : (sent as TransferErrorCode);
    }
    if (!isSameCurrency) {
      const received = validateAmount(draft.received);
      if (received !== null) {
        return received === "AMOUNT_REQUIRED"
          ? "RECEIVED_REQUIRED"
          : (received as TransferErrorCode);
      }
    }
    return draft.occurredOn ? null : "DATE_REQUIRED";
  }

  return (
    <form
      className={cx(styles.form)}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        const invalid = validate();
        setLocalError(invalid);
        const sent = toDecimalString(draft.sent);
        // Misma moneda: lo que entra es lo que sale, salvo que se diga otra cosa.
        const received = isSameCurrency ? sent : toDecimalString(draft.received);
        if (!invalid && sent !== null && received !== null) {
          onSubmit({ sent, received, draft });
        }
      }}
    >
      {field === "form" ? <Alert>{message}</Alert> : null}
      <Select
        label={t("transfers.form.from")}
        placeholder={t("transfers.form.accountPlaceholder")}
        options={accounts.map((row) => ({ id: row.id, label: `${row.name} (${row.currency})` }))}
        value={draft.fromAccountId || null}
        onChange={(value) => {
          update({ fromAccountId: value });
        }}
        {...(field === "accounts" ? { errorMessage: message } : {})}
      />
      <Select
        label={t("transfers.form.to")}
        placeholder={t("transfers.form.accountPlaceholder")}
        options={accounts.map((row) => ({ id: row.id, label: `${row.name} (${row.currency})` }))}
        value={draft.toAccountId || null}
        onChange={(value) => {
          update({ toAccountId: value });
        }}
      />
      <TextField
        label={isSameCurrency ? t("transfers.form.amount") : t("transfers.form.sent")}
        description={t("transfers.form.amountHelp", { currency: origin?.currency ?? "" })}
        value={draft.sent}
        onChange={(value) => {
          update({ sent: value });
        }}
        inputMode="decimal"
        autoComplete="off"
        isRequired
        validationBehavior="aria"
        {...(field === "sent" ? { errorMessage: message } : {})}
      />
      {isSameCurrency ? null : (
        <TextField
          label={t("transfers.form.received")}
          description={t("transfers.form.receivedHelp", {
            currency: destination?.currency ?? "",
          })}
          value={draft.received}
          onChange={(value) => {
            update({ received: value });
          }}
          inputMode="decimal"
          autoComplete="off"
          isRequired
          validationBehavior="aria"
          {...(field === "received" ? { errorMessage: message } : {})}
        />
      )}
      <DateField
        label={t("transfers.form.date")}
        description={t("transfers.form.dateHelp")}
        value={draft.occurredOn}
        max={today()}
        onChange={(value) => {
          update({ occurredOn: value });
        }}
        {...(field === "date" ? { errorMessage: message } : {})}
      />
      <TextField
        label={t("transfers.form.description")}
        description={t("transfers.form.descriptionHelp")}
        value={draft.description}
        onChange={(value) => {
          update({ description: value });
        }}
        maxLength={DESCRIPTION_MAX_LENGTH}
        autoComplete="off"
        validationBehavior="aria"
        {...(field === "description" ? { errorMessage: message } : {})}
      />
      <div className={cx(styles.actions)}>
        <Button type="submit" isDisabled={isPending}>
          {isPending ? submittingLabel : submitLabel}
        </Button>
      </div>
    </form>
  );
}
