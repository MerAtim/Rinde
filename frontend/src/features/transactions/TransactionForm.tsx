import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { DateField } from "../../shared/ui/DateField";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import { Select } from "../../shared/ui/Select";
import { TextField } from "../../shared/ui/TextField";
import type { Account } from "../accounts/api";
import styles from "./Transactions.module.css";
import {
  type Category,
  DESCRIPTION_MAX_LENGTH,
  TRANSACTION_KINDS,
  type TransactionErrorCode,
  type TransactionKind,
} from "./api";
import { errorCodeOf, fieldOf, toDecimalString, validateAmount } from "./errors";
import { today, useCategoryName } from "./presentation";

export interface TransactionDraft {
  accountId: string;
  kind: TransactionKind;
  amount: string;
  categoryId: string;
  occurredOn: string;
  description: string;
}

interface TransactionFormProps {
  accounts: Account[];
  categories: Category[];
  draft: TransactionDraft;
  /** En la edición la cuenta queda fija: mover plata de cuenta es otra operación. */
  isAccountFixed?: boolean;
  submitLabel: string;
  submittingLabel: string;
  isPending: boolean;
  error: unknown;
  onSubmit: (values: { amount: string; draft: TransactionDraft }) => void;
}

export function TransactionForm({
  accounts,
  categories,
  draft: initial,
  isAccountFixed = false,
  submitLabel,
  submittingLabel,
  isPending,
  error,
  onSubmit,
}: TransactionFormProps) {
  const { t } = useTranslation();
  const categoryName = useCategoryName();
  const [draft, setDraft] = useState(initial);
  const [localError, setLocalError] = useState<TransactionErrorCode | null>(null);

  const code = localError ?? errorCodeOf(error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`transactions.errors.${code}`) : "";
  const account = accounts.find((row) => row.id === draft.accountId);
  const categoriesOfKind = categories.filter((row) => row.kind === draft.kind);

  function update(changes: Partial<TransactionDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
    setLocalError(null);
  }

  return (
    <form
      className={cx(styles.form)}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        const invalid =
          validateAmount(draft.amount) ??
          (draft.categoryId ? null : "CATEGORY_REQUIRED") ??
          (draft.occurredOn ? null : "DATE_REQUIRED");
        setLocalError(invalid);
        const amount = toDecimalString(draft.amount);
        if (!invalid && amount !== null) {
          onSubmit({ amount, draft });
        }
      }}
    >
      {field === "form" ? <Alert>{message}</Alert> : null}
      <Select
        label={t("transactions.form.account")}
        placeholder={t("transactions.form.accountPlaceholder")}
        options={accounts.map((row) => ({ id: row.id, label: `${row.name} (${row.currency})` }))}
        value={draft.accountId || null}
        isDisabled={isAccountFixed}
        onChange={(value) => {
          update({ accountId: value });
        }}
        {...(field === "account" ? { errorMessage: message } : {})}
      />
      <SegmentedButton
        label={t("transactions.form.kind")}
        isLabelVisible
        options={TRANSACTION_KINDS.map((kind) => ({
          id: kind,
          label: t(`transactions.kind.${kind}`),
        }))}
        value={draft.kind}
        onChange={(kind) => {
          // Las categorías son de un tipo: al cambiarlo, la elegida deja de valer.
          update({ kind, categoryId: "" });
        }}
      />
      <TextField
        label={t("transactions.form.amount")}
        description={t("transactions.form.amountHelp", { currency: account?.currency ?? "" })}
        value={draft.amount}
        onChange={(value) => {
          update({ amount: value });
        }}
        inputMode="decimal"
        autoComplete="off"
        isRequired
        validationBehavior="aria"
        {...(field === "amount" ? { errorMessage: message } : {})}
      />
      <Select
        label={t("transactions.form.category")}
        placeholder={t("transactions.form.categoryPlaceholder")}
        options={categoriesOfKind.map((row) => ({ id: row.id, label: categoryName(row) }))}
        value={draft.categoryId || null}
        onChange={(value) => {
          update({ categoryId: value });
        }}
        {...(field === "category" ? { errorMessage: message } : {})}
      />
      <DateField
        label={t("transactions.form.date")}
        description={t("transactions.form.dateHelp")}
        value={draft.occurredOn}
        max={today()}
        onChange={(value) => {
          update({ occurredOn: value });
        }}
        {...(field === "date" ? { errorMessage: message } : {})}
      />
      <TextField
        label={t("transactions.form.description")}
        description={t("transactions.form.descriptionHelp")}
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
