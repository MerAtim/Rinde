import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";

import { useShortDateFormatter } from "../../i18n/format";
import { announcementFrom } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { cx } from "../../shared/ui/cx";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import { StatusChip } from "../../shared/ui/StatusChip";
import { useAccounts } from "../accounts/useAccounts";
import { useCategoryName } from "../transactions/presentation";
import { useCategories } from "../transactions/useTransactions";
import type { RecurringRule } from "./api";
import styles from "./Recurring.module.css";
import { useCancelRule, useRules } from "./useRecurring";

/**
 * Los movimientos recurrentes (ADR-0027): cada regla con su monto, cada cuánto
 * se repite y la próxima vez que se registra sola.
 */
export function RecurringPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const rules = useRules();
  const announcement = announcementFrom(location.state);

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/transactions" variant="text" icon="arrow-back">
          {t("recurring.backToTransactions")}
        </LinkButton>
      </div>
      <header className={cx(styles.header)}>
        <div className={cx(styles.heading)}>
          <h1 className={cx(styles.title)}>{t("recurring.title")}</h1>
          <p className={cx(styles.subtitle)}>{t("recurring.subtitle")}</p>
        </div>
        {rules.isSuccess && rules.data.length > 0 ? (
          <LinkButton to="/recurring/new" icon="add">
            {t("recurring.new")}
          </LinkButton>
        ) : null}
      </header>
      {announcement ? (
        <p role="status" className={cx(styles.announcement)}>
          {announcement}
        </p>
      ) : null}
      {rules.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("recurring.loading")}
        </p>
      ) : null}
      {rules.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>{t("recurring.loadError")}</Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void rules.refetch();
            }}
          >
            {t("recurring.retry")}
          </Button>
        </div>
      ) : null}
      {rules.isSuccess && rules.data.length === 0 ? (
        <section className={cx(styles.empty)} aria-labelledby="recurring-empty">
          <h2 id="recurring-empty" className={cx(styles.emptyTitle)}>
            {t("recurring.emptyTitle")}
          </h2>
          <p className={cx(styles.subtitle)}>{t("recurring.emptyBody")}</p>
          <LinkButton to="/recurring/new" icon="add">
            {t("recurring.new")}
          </LinkButton>
        </section>
      ) : null}
      {rules.isSuccess && rules.data.length > 0 ? (
        <ul className={cx(styles.rules)}>
          {rules.data.map((rule) => (
            <RuleCard key={rule.id} rule={rule} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function RuleCard({ rule }: { rule: RecurringRule }) {
  const { t } = useTranslation();
  const formatDate = useShortDateFormatter();
  const categoryName = useCategoryName();
  const categories = useCategories();
  const accounts = useAccounts(true);
  const cancel = useCancelRule();
  const [isConfirming, setConfirming] = useState(false);

  const category = categories.data?.find((row) => row.id === rule.category_id);
  const account = accounts.data?.find((row) => row.id === rule.account_id);
  const title = rule.description ?? (category ? categoryName(category) : t("recurring.untitled"));
  const headingId = `rule-${rule.id}`;

  return (
    <li className={cx(styles.rule)} aria-labelledby={headingId}>
      <div className={cx(styles.ruleHeader)}>
        <div>
          <h2 id={headingId} className={cx(styles.ruleTitle)}>
            {title}
          </h2>
          <p className={cx(styles.muted)}>
            {t(`recurring.frequency.${rule.frequency}`)}
            {` · ${t("recurring.since", { date: formatDate(rule.starts_on) })}`}
            {account ? ` · ${account.name}` : ""}
          </p>
        </div>
        {rule.cancelled_at ? (
          <StatusChip tone="neutral" icon="close" label={t("recurring.cancelled")} />
        ) : null}
      </div>
      <dl className={cx(styles.figures)}>
        <div className={cx(styles.figure)}>
          <dt>{t("recurring.amount")}</dt>
          <dd>
            <MoneyAmount
              amount={rule.amount}
              currency={rule.currency}
              tone={rule.kind === "income" ? "income" : "expense"}
            />
          </dd>
        </div>
        <div className={cx(styles.figure)}>
          <dt>{t("recurring.generated")}</dt>
          <dd>{t("recurring.generatedValue", { count: rule.generated })}</dd>
        </div>
        {rule.next_on ? (
          <div className={cx(styles.figure)}>
            <dt>{t("recurring.next")}</dt>
            <dd>{formatDate(rule.next_on)}</dd>
          </div>
        ) : null}
      </dl>
      {rule.cancelled_at ? null : (
        <div className={cx(styles.ruleActions)}>
          <LinkButton
            to={`/recurring/${rule.id}`}
            variant="text"
            icon="edit"
            aria-label={t("recurring.changeNamed", { name: title })}
          >
            {t("recurring.change")}
          </LinkButton>
          <Button
            variant="text"
            onPress={() => {
              setConfirming(true);
            }}
          >
            {t("recurring.cancel")}
          </Button>
        </div>
      )}
      <ConfirmDialog
        isOpen={isConfirming}
        onOpenChange={setConfirming}
        title={t("recurring.cancelTitle", { name: title })}
        confirmLabel={t("recurring.cancelConfirm")}
        cancelLabel={t("recurring.cancelKeep")}
        isPending={cancel.isPending}
        onConfirm={() => {
          cancel.mutate(rule.id, {
            onSuccess: () => {
              setConfirming(false);
            },
          });
        }}
      >
        {t("recurring.cancelBody")}
      </ConfirmDialog>
    </li>
  );
}
