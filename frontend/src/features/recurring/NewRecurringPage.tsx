import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { DateField } from "../../shared/ui/DateField";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import { Select } from "../../shared/ui/Select";
import { TextField } from "../../shared/ui/TextField";
import { useAccounts } from "../accounts/useAccounts";
import {
  DESCRIPTION_MAX_LENGTH,
  TRANSACTION_KINDS,
  type TransactionKind,
} from "../transactions/api";
import { toDecimalString, validateAmount } from "../transactions/errors";
import { today, useCategoryName } from "../transactions/presentation";
import { useCategories } from "../transactions/useTransactions";
import { FREQUENCIES, type Frequency, type RecurringErrorCode } from "./api";
import { errorCodeOf, fieldOf, type RecurringField } from "./errors";
import styles from "./Recurring.module.css";
import { useCreateRule } from "./useRecurring";

/**
 * Un movimiento recurrente nuevo (ADR-0027). Lo que ya venció desde la primera
 * vez se registra al guardar; lo demás, solo, cuando llega su fecha.
 */
export function NewRecurringPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const categoryName = useCategoryName();
  // Solo cuentas activas: una archivada no recibe movimientos nuevos.
  const accounts = useAccounts(false);
  const categories = useCategories();
  const create = useCreateRule();
  const rows = accounts.data ?? [];
  const [values, setValues] = useState<{
    accountId: string;
    kind: TransactionKind;
    amount: string;
    categoryId: string;
    frequency: Frequency;
    startsOn: string;
    description: string;
  }>({
    accountId: "",
    kind: "expense",
    amount: "",
    categoryId: "",
    frequency: "monthly",
    startsOn: today(),
    description: "",
  });
  const [localError, setLocalError] = useState<RecurringErrorCode | null>(null);

  // Sin elegir, la primera cuenta activa: un string vacío no es una cuenta.
  const accountId = values.accountId !== "" ? values.accountId : (rows[0]?.id ?? "");
  const account = rows.find((row) => row.id === accountId);
  const code = localError ?? errorCodeOf(create.error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`recurring.errors.${code}`) : "";

  function update(changes: Partial<typeof values>) {
    setValues((current) => ({ ...current, ...changes }));
    setLocalError(null);
  }

  function errorFor(name: RecurringField) {
    return field === name ? { errorMessage: message } : {};
  }

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/recurring" variant="text" icon="arrow-back">
          {t("recurring.form.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("recurring.form.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("recurring.form.subtitle")}</p>
      </div>
      {accounts.isSuccess && rows.length === 0 ? (
        <section className={cx(styles.empty)} aria-labelledby="no-accounts">
          <h2 id="no-accounts" className={cx(styles.emptyTitle)}>
            {t("transactions.form.noAccountsTitle")}
          </h2>
          <p className={cx(styles.subtitle)}>{t("transactions.form.noAccountsBody")}</p>
          <LinkButton to="/accounts/new" icon="add">
            {t("transactions.form.noAccountsAction")}
          </LinkButton>
        </section>
      ) : null}
      {rows.length > 0 && categories.isSuccess ? (
        <form
          className={cx(styles.form)}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            const invalid =
              validateAmount(values.amount) ??
              (values.categoryId ? null : "CATEGORY_REQUIRED") ??
              (values.startsOn ? null : "DATE_REQUIRED");
            setLocalError(invalid);
            const amount = toDecimalString(values.amount);
            if (invalid || amount === null) return;
            create.mutate(
              {
                input: {
                  account_id: accountId,
                  kind: values.kind,
                  amount,
                  category_id: values.categoryId,
                  frequency: values.frequency,
                  starts_on: values.startsOn,
                  description: values.description.trim() || null,
                },
                // Una clave por intento: si el pedido se pierde y se vuelve a
                // tocar, no se duplica la regla.
                idempotencyKey: crypto.randomUUID(),
              },
              {
                onSuccess: () => {
                  void navigate("/recurring", {
                    state: withAnnouncement(t("recurring.created")),
                  });
                },
              },
            );
          }}
        >
          {field === "form" ? <Alert>{message}</Alert> : null}
          <Select
            label={t("transactions.form.account")}
            placeholder={t("transactions.form.accountPlaceholder")}
            options={rows.map((row) => ({ id: row.id, label: `${row.name} (${row.currency})` }))}
            value={accountId || null}
            onChange={(value) => {
              update({ accountId: value });
            }}
            {...errorFor("account")}
          />
          <SegmentedButton
            label={t("transactions.form.kind")}
            isLabelVisible
            options={TRANSACTION_KINDS.map((kind) => ({
              id: kind,
              label: t(`transactions.kind.${kind}`),
            }))}
            value={values.kind}
            onChange={(kind) => {
              // Las categorías son de un tipo: al cambiarlo, la elegida deja de valer.
              update({ kind, categoryId: "" });
            }}
          />
          <TextField
            label={t("transactions.form.amount")}
            description={t("recurring.form.amountHelp", { currency: account?.currency ?? "" })}
            value={values.amount}
            onChange={(value) => {
              update({ amount: value });
            }}
            inputMode="decimal"
            autoComplete="off"
            isRequired
            validationBehavior="aria"
            {...errorFor("amount")}
          />
          <Select
            label={t("transactions.form.category")}
            placeholder={t("transactions.form.categoryPlaceholder")}
            options={categories.data
              .filter((row) => row.kind === values.kind)
              .map((row) => ({ id: row.id, label: categoryName(row) }))}
            value={values.categoryId || null}
            onChange={(value) => {
              update({ categoryId: value });
            }}
            {...errorFor("category")}
          />
          <Select
            label={t("recurring.form.frequency")}
            placeholder={t("recurring.form.frequencyPlaceholder")}
            options={FREQUENCIES.map((frequency) => ({
              id: frequency,
              label: t(`recurring.frequency.${frequency}`),
            }))}
            value={values.frequency}
            onChange={(value) => {
              const chosen = FREQUENCIES.find((frequency) => frequency === value);
              if (chosen) update({ frequency: chosen });
            }}
          />
          <DateField
            label={t("recurring.form.startsOn")}
            description={t("recurring.form.startsOnHelp")}
            value={values.startsOn}
            onChange={(value) => {
              update({ startsOn: value });
            }}
            {...errorFor("date")}
          />
          <TextField
            label={t("transactions.form.description")}
            description={t("recurring.form.descriptionHelp")}
            value={values.description}
            onChange={(value) => {
              update({ description: value });
            }}
            maxLength={DESCRIPTION_MAX_LENGTH}
            autoComplete="off"
            validationBehavior="aria"
            {...errorFor("description")}
          />
          <div className={cx(styles.actions)}>
            <Button type="submit" isDisabled={create.isPending}>
              {create.isPending ? t("recurring.form.submitting") : t("recurring.form.submit")}
            </Button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
