import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import { Select } from "../../shared/ui/Select";
import { TextField } from "../../shared/ui/TextField";
import { usePreferences } from "../preferences/usePreferences";
import type { Category } from "../transactions/api";
import { toDecimalString } from "../transactions/errors";
import { useCategoryName } from "../transactions/presentation";
import { useCategories } from "../transactions/useTransactions";
import {
  BUDGET_CURRENCIES,
  type Budget,
  type BudgetCurrency,
  type BudgetErrorCode,
  isBudgetsApiError,
} from "./api";
import styles from "./Budgets.module.css";
import { useBudgets, useSetBudget } from "./useBudgets";

/** Los que valida la pantalla antes de enviar. El servidor sigue siendo la autoridad. */
type LocalErrorCode = "AMOUNT_REQUIRED" | "AMOUNT_INVALID" | "CATEGORY_REQUIRED";
type FormErrorCode = BudgetErrorCode | LocalErrorCode;

const AMOUNT_ERRORS: readonly FormErrorCode[] = [
  "AMOUNT_REQUIRED",
  "AMOUNT_INVALID",
  "AMOUNT_TOO_PRECISE",
  "BUDGET_AMOUNT_INVALID",
];
const CATEGORY_ERRORS: readonly FormErrorCode[] = [
  "CATEGORY_REQUIRED",
  "BUDGET_CATEGORY_NOT_FOUND",
  "BUDGET_CATEGORY_NOT_EXPENSE",
];

function validateAmount(typed: string): LocalErrorCode | "BUDGET_AMOUNT_INVALID" | null {
  if (!typed.trim()) {
    return "AMOUNT_REQUIRED";
  }
  const decimal = toDecimalString(typed);
  if (decimal === null) {
    return "AMOUNT_INVALID";
  }
  // Cero escrito de cualquier forma, sin convertir a número (ADR-0002).
  return /^0*(\.0*)?$/.test(decimal) ? "BUDGET_AMOUNT_INVALID" : null;
}

/** El monto del servidor, para editarlo con la coma decimal que se escribe acá. */
function editable(amount: string): string {
  return amount.replace(".", ",");
}

/**
 * Fijar un tope nuevo (`/budgets/new`) o cambiar uno (`/budgets/:categoryId/edit`).
 * Siempre vale desde el mes en curso (ADR-0021).
 */
export function BudgetFormPage() {
  const { t } = useTranslation();
  const { categoryId } = useParams();
  const categories = useCategories();
  const budgets = useBudgets(null);
  const preferences = usePreferences();
  const isEdit = categoryId !== undefined;

  const isPending = categories.isPending || budgets.isPending || preferences.isPending;
  const isError = categories.isError || budgets.isError;
  const existing = budgets.data?.budgets.find((budget) => budget.category.id === categoryId);

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/budgets" variant="text" icon="arrow-back">
          {t("budgets.form.back")}
        </LinkButton>
      </div>
      {isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("budgets.loading")}
        </p>
      ) : null}
      {isError ? <Alert>{t("budgets.loadError")}</Alert> : null}
      {!isPending && !isError && isEdit && !existing ? (
        <Alert>{t("budgets.form.notFound")}</Alert>
      ) : null}
      {/* El formulario arranca con lo guardado: se monta recién cuando llegó. */}
      {categories.isSuccess && budgets.isSuccess && !isPending && (!isEdit || existing) ? (
        <BudgetForm
          categories={categories.data}
          budgets={budgets.data.budgets}
          existing={existing}
          // Las preferencias solo dan la moneda inicial: si no cargan, pesos.
          defaultCurrency={preferences.data?.reference_currency ?? "ARS"}
        />
      ) : null}
    </div>
  );
}

interface BudgetFormProps {
  categories: Category[];
  budgets: Budget[];
  existing: Budget | undefined;
  defaultCurrency: BudgetCurrency;
}

function BudgetForm({ categories, budgets, existing, defaultCurrency }: BudgetFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const categoryName = useCategoryName();
  const save = useSetBudget();
  const [categoryId, setCategoryId] = useState(existing?.category.id ?? "");
  const [amount, setAmount] = useState(existing ? editable(existing.limit.amount) : "");
  const [currency, setCurrency] = useState<BudgetCurrency>(
    existing?.limit.currency === "USD" ? "USD" : existing ? "ARS" : defaultCurrency,
  );
  const [localError, setLocalError] = useState<FormErrorCode | null>(null);

  const serverError: FormErrorCode | null = save.error
    ? isBudgetsApiError(save.error)
      ? save.error.code
      : "UNKNOWN_ERROR"
    : null;
  const code = localError ?? serverError;
  const message = code ? t(`budgets.errors.${code}`) : "";
  const field = code
    ? AMOUNT_ERRORS.includes(code)
      ? "amount"
      : CATEGORY_ERRORS.includes(code)
        ? "category"
        : "form"
    : null;

  // Una categoría con tope se cambia desde su fila, no se elige de nuevo.
  const budgeted = new Set(budgets.map((budget) => budget.category.id));
  const available = categories.filter((row) => row.kind === "expense" && !budgeted.has(row.id));
  const title = existing
    ? t("budgets.form.editTitle", { name: categoryName(existing.category) })
    : t("budgets.form.newTitle");

  function clearErrors() {
    setLocalError(null);
    save.reset();
  }

  return (
    <>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{title}</h1>
        <p className={cx(styles.subtitle)}>{t("budgets.form.subtitle")}</p>
      </div>
      {field === "form" ? <Alert>{message}</Alert> : null}
      {!existing && available.length === 0 ? (
        <p className={cx(styles.muted)}>{t("budgets.form.noCategories")}</p>
      ) : (
        <form
          className={cx(styles.form)}
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            const invalid = validateAmount(amount) ?? (categoryId ? null : "CATEGORY_REQUIRED");
            setLocalError(invalid);
            const decimal = toDecimalString(amount);
            if (invalid || decimal === null) {
              return;
            }
            const category = categories.find((row) => row.id === categoryId);
            save.mutate(
              { categoryId, input: { amount: decimal, currency } },
              {
                onSuccess: () => {
                  void navigate("/budgets", {
                    state: withAnnouncement(
                      t("budgets.form.saved", { name: category ? categoryName(category) : "" }),
                    ),
                  });
                },
              },
            );
          }}
        >
          {existing ? null : (
            <Select
              label={t("budgets.form.category")}
              placeholder={t("budgets.form.categoryPlaceholder")}
              options={available.map((row) => ({ id: row.id, label: categoryName(row) }))}
              value={categoryId || null}
              onChange={(value) => {
                setCategoryId(value);
                clearErrors();
              }}
              {...(field === "category" ? { errorMessage: message } : {})}
            />
          )}
          <TextField
            label={t("budgets.form.amount")}
            description={t("budgets.form.amountHelp")}
            value={amount}
            onChange={(value) => {
              setAmount(value);
              clearErrors();
            }}
            inputMode="decimal"
            autoComplete="off"
            isRequired
            validationBehavior="aria"
            {...(field === "amount" ? { errorMessage: message } : {})}
          />
          <SegmentedButton
            label={t("budgets.form.currency")}
            isLabelVisible
            description={t("budgets.form.currencyHelp")}
            options={BUDGET_CURRENCIES.map((id) => ({
              id,
              label: id,
              accessibleLabel: t(`accounts.currency.${id}`),
            }))}
            value={currency}
            onChange={(value) => {
              setCurrency(value);
              clearErrors();
            }}
          />
          <div className={cx(styles.formActions)}>
            <Button type="submit" isDisabled={save.isPending}>
              {save.isPending ? t("budgets.form.submitting") : t("budgets.form.submit")}
            </Button>
          </div>
        </form>
      )}
    </>
  );
}
