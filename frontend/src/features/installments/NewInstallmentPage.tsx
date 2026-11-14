import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { DateField } from "../../shared/ui/DateField";
import { Select } from "../../shared/ui/Select";
import { TextField } from "../../shared/ui/TextField";
import { useAccounts } from "../accounts/useAccounts";
import { DESCRIPTION_MAX_LENGTH } from "../transactions/api";
import { toDecimalString } from "../transactions/errors";
import { today, useCategoryName } from "../transactions/presentation";
import { useCategories } from "../transactions/useTransactions";
import { type InstallmentErrorCode, isInstallmentsApiError, MAX_COUNT, MIN_COUNT } from "./api";
import styles from "./Installments.module.css";
import { useCreatePlan } from "./useInstallments";

type Field = "account" | "total" | "count" | "category" | "date" | "description" | "form";

const FIELD_BY_CODE: Partial<Record<InstallmentErrorCode, Field>> = {
  ACCOUNT_NOT_FOUND: "account",
  ACCOUNT_ARCHIVED: "account",
  AMOUNT_REQUIRED: "total",
  AMOUNT_INVALID: "total",
  AMOUNT_TOO_PRECISE: "total",
  TRANSACTION_AMOUNT_NOT_POSITIVE: "total",
  TRANSACTION_CURRENCY_MISMATCH: "total",
  INSTALLMENT_AMOUNT_TOO_SMALL: "total",
  INSTALLMENT_COUNT_INVALID: "count",
  CATEGORY_REQUIRED: "category",
  CATEGORY_NOT_FOUND: "category",
  CATEGORY_KIND_MISMATCH: "category",
  DATE_REQUIRED: "date",
  TRANSACTION_DATE_IN_FUTURE: "date",
  TRANSACTION_DESCRIPTION_INVALID: "description",
};

/** Las opciones de cantidad: de 2 a 48, como acepta el servidor (ADR-0026). */
const COUNTS = Array.from({ length: MAX_COUNT - MIN_COUNT + 1 }, (_, index) => MIN_COUNT + index);

function errorCodeOf(error: unknown): InstallmentErrorCode | null {
  if (error === null || error === undefined) return null;
  return isInstallmentsApiError(error) ? error.code : "UNKNOWN_ERROR";
}

/**
 * Una compra en cuotas. Se escribe el total y la cantidad: el reparto exacto lo
 * hace el servidor y se ve en la pantalla de cuotas, sin cuentas en el navegador.
 */
export function NewInstallmentPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const categoryName = useCategoryName();
  // Solo cuentas activas: en una archivada no se registran compras nuevas.
  const accounts = useAccounts(false);
  const categories = useCategories();
  const create = useCreatePlan();
  const rows = accounts.data ?? [];
  const [values, setValues] = useState({
    accountId: "",
    total: "",
    count: "",
    categoryId: "",
    firstOn: today(),
    description: "",
  });
  const [localError, setLocalError] = useState<InstallmentErrorCode | null>(null);

  // Sin elegir, la primera cuenta activa: un string vacío no es una cuenta.
  const accountId = values.accountId !== "" ? values.accountId : (rows[0]?.id ?? "");
  const account = rows.find((row) => row.id === accountId);
  const code = localError ?? errorCodeOf(create.error);
  const field = code ? (FIELD_BY_CODE[code] ?? "form") : null;
  const message = code ? t(`installments.errors.${code}`) : "";

  function update(changes: Partial<typeof values>) {
    setValues((current) => ({ ...current, ...changes }));
    setLocalError(null);
  }

  function errorFor(name: Field) {
    return field === name ? { errorMessage: message } : {};
  }

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/installments" variant="text" icon="arrow-back">
          {t("installments.form.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("installments.form.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("installments.form.subtitle")}</p>
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
            const total = toDecimalString(values.total);
            const invalid: InstallmentErrorCode | null = !values.total.trim()
              ? "AMOUNT_REQUIRED"
              : total === null
                ? "AMOUNT_INVALID"
                : !values.count
                  ? "INSTALLMENT_COUNT_INVALID"
                  : !values.categoryId
                    ? "CATEGORY_REQUIRED"
                    : !values.firstOn
                      ? "DATE_REQUIRED"
                      : null;
            setLocalError(invalid);
            if (invalid || total === null) return;
            create.mutate(
              {
                input: {
                  account_id: accountId,
                  category_id: values.categoryId,
                  total,
                  count: Number(values.count),
                  first_on: values.firstOn,
                  description: values.description.trim() || null,
                },
                // Una clave por intento: si el pedido se pierde y se vuelve a
                // tocar, no se duplica la compra.
                idempotencyKey: crypto.randomUUID(),
              },
              {
                onSuccess: () => {
                  void navigate("/installments", {
                    state: withAnnouncement(t("installments.created")),
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
          <TextField
            label={t("installments.form.total")}
            description={t("installments.form.totalHelp", { currency: account?.currency ?? "" })}
            value={values.total}
            onChange={(value) => {
              update({ total: value });
            }}
            inputMode="decimal"
            autoComplete="off"
            isRequired
            validationBehavior="aria"
            {...errorFor("total")}
          />
          <Select
            label={t("installments.form.count")}
            placeholder={t("installments.form.countPlaceholder")}
            options={COUNTS.map((count) => ({
              id: String(count),
              label: t("installments.form.countOption", { count }),
            }))}
            value={values.count || null}
            onChange={(value) => {
              update({ count: value });
            }}
            {...errorFor("count")}
          />
          <Select
            label={t("transactions.form.category")}
            placeholder={t("transactions.form.categoryPlaceholder")}
            options={categories.data
              .filter((row) => row.kind === "expense")
              .map((row) => ({ id: row.id, label: categoryName(row) }))}
            value={values.categoryId || null}
            onChange={(value) => {
              update({ categoryId: value });
            }}
            {...errorFor("category")}
          />
          <DateField
            label={t("installments.form.firstOn")}
            description={t("installments.form.firstOnHelp")}
            value={values.firstOn}
            max={today()}
            onChange={(value) => {
              update({ firstOn: value });
            }}
            {...errorFor("date")}
          />
          <TextField
            label={t("transactions.form.description")}
            description={t("installments.form.descriptionHelp")}
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
              {create.isPending ? t("installments.form.submitting") : t("installments.form.submit")}
            </Button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
