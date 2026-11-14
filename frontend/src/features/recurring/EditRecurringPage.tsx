import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { TextField } from "../../shared/ui/TextField";
import { DESCRIPTION_MAX_LENGTH } from "../transactions/api";
import { toDecimalString, validateAmount } from "../transactions/errors";
import type { RecurringErrorCode, RecurringRule } from "./api";
import { errorCodeOf, fieldOf, type RecurringField } from "./errors";
import styles from "./Recurring.module.css";
import { useChangeRule, useRules } from "./useRecurring";

/**
 * Cambiar el monto de un movimiento recurrente: el alquiler aumentó (ADR-0027).
 * El resto no se cambia; para eso se cancela y se crea otro.
 */
export function EditRecurringPage() {
  const { t } = useTranslation();
  const { ruleId = "" } = useParams();
  const rules = useRules();
  const rule = rules.data?.find((row) => row.id === ruleId && row.cancelled_at === null);

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/recurring" variant="text" icon="arrow-back">
          {t("recurring.form.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("recurring.edit.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("recurring.edit.subtitle")}</p>
      </div>
      {rules.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("recurring.loading")}
        </p>
      ) : null}
      {rules.isError ? <Alert>{t("recurring.loadError")}</Alert> : null}
      {/* Una regla ajena, inexistente o cancelada se informa igual. */}
      {rules.isSuccess && !rule ? (
        <Alert>{t("recurring.errors.RECURRING_RULE_NOT_FOUND")}</Alert>
      ) : null}
      {rule ? <ChangeForm rule={rule} /> : null}
    </div>
  );
}

function ChangeForm({ rule }: { rule: RecurringRule }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const change = useChangeRule(rule.id);
  const [amount, setAmount] = useState(rule.amount);
  const [description, setDescription] = useState(rule.description ?? "");
  const [localError, setLocalError] = useState<RecurringErrorCode | null>(null);

  const code = localError ?? errorCodeOf(change.error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`recurring.errors.${code}`) : "";

  function errorFor(name: RecurringField) {
    return field === name ? { errorMessage: message } : {};
  }

  return (
    <form
      className={cx(styles.form)}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        const invalid = validateAmount(amount);
        setLocalError(invalid);
        const decimal = toDecimalString(amount);
        if (invalid || decimal === null) return;
        change.mutate(
          { amount: decimal, description: description.trim() || null },
          {
            onSuccess: () => {
              void navigate("/recurring", {
                state: withAnnouncement(t("recurring.changed")),
              });
            },
          },
        );
      }}
    >
      {field === "form" ? <Alert>{message}</Alert> : null}
      <TextField
        label={t("recurring.edit.amount")}
        description={t("recurring.edit.amountHelp", { currency: rule.currency })}
        value={amount}
        onChange={(value) => {
          setAmount(value);
          setLocalError(null);
        }}
        inputMode="decimal"
        autoComplete="off"
        isRequired
        validationBehavior="aria"
        {...errorFor("amount")}
      />
      <TextField
        label={t("transactions.form.description")}
        description={t("recurring.form.descriptionHelp")}
        value={description}
        onChange={(value) => {
          setDescription(value);
          setLocalError(null);
        }}
        maxLength={DESCRIPTION_MAX_LENGTH}
        autoComplete="off"
        validationBehavior="aria"
        {...errorFor("description")}
      />
      <div className={cx(styles.actions)}>
        <Button type="submit" isDisabled={change.isPending}>
          {change.isPending ? t("recurring.form.submitting") : t("recurring.edit.submit")}
        </Button>
      </div>
    </form>
  );
}
