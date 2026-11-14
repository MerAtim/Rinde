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
import { TableScroll } from "../../shared/ui/TableScroll";
import { useAccounts } from "../accounts/useAccounts";
import { useCategoryName } from "../transactions/presentation";
import { useCategories } from "../transactions/useTransactions";
import type { InstallmentPlan, ScheduledInstallment } from "./api";
import styles from "./Installments.module.css";
import { useCancelPlan, usePlans } from "./useInstallments";

/**
 * Las compras en cuotas (ADR-0026): cuánto falta, cuántas cuotas ya son
 * movimientos y el calendario de cada una. Los montos los calcula el servidor.
 */
export function InstallmentsPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const plans = usePlans();
  const announcement = announcementFrom(location.state);

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/transactions" variant="text" icon="arrow-back">
          {t("installments.backToTransactions")}
        </LinkButton>
      </div>
      <header className={cx(styles.header)}>
        <div className={cx(styles.heading)}>
          <h1 className={cx(styles.title)}>{t("installments.title")}</h1>
          <p className={cx(styles.subtitle)}>{t("installments.subtitle")}</p>
        </div>
        {plans.isSuccess && plans.data.length > 0 ? (
          <LinkButton to="/installments/new" icon="add">
            {t("installments.new")}
          </LinkButton>
        ) : null}
      </header>
      {announcement ? (
        <p role="status" className={cx(styles.announcement)}>
          {announcement}
        </p>
      ) : null}
      {plans.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("installments.loading")}
        </p>
      ) : null}
      {plans.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>{t("installments.loadError")}</Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void plans.refetch();
            }}
          >
            {t("installments.retry")}
          </Button>
        </div>
      ) : null}
      {plans.isSuccess && plans.data.length === 0 ? (
        <section className={cx(styles.empty)} aria-labelledby="installments-empty">
          <h2 id="installments-empty" className={cx(styles.emptyTitle)}>
            {t("installments.emptyTitle")}
          </h2>
          <p className={cx(styles.subtitle)}>{t("installments.emptyBody")}</p>
          <LinkButton to="/installments/new" icon="add">
            {t("installments.new")}
          </LinkButton>
        </section>
      ) : null}
      {plans.isSuccess && plans.data.length > 0 ? (
        <ul className={cx(styles.plans)}>
          {plans.data.map((plan) => (
            <PlanCard key={plan.id} plan={plan} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function PlanCard({ plan }: { plan: InstallmentPlan }) {
  const { t } = useTranslation();
  const formatDate = useShortDateFormatter();
  const categoryName = useCategoryName();
  const categories = useCategories();
  const accounts = useAccounts(true);
  const cancel = useCancelPlan();
  const [isConfirming, setConfirming] = useState(false);

  const category = categories.data?.find((row) => row.id === plan.category_id);
  const account = accounts.data?.find((row) => row.id === plan.account_id);
  const title =
    plan.description ?? (category ? categoryName(category) : t("installments.untitled"));
  const generated = plan.installments.filter((item) => item.transaction_id !== null).length;
  const next = plan.cancelled_at
    ? undefined
    : plan.installments.find((item) => item.transaction_id === null);
  const isFinished = !plan.cancelled_at && next === undefined;
  const headingId = `plan-${plan.id}`;

  return (
    <li className={cx(styles.plan)} aria-labelledby={headingId}>
      <div className={cx(styles.planHeader)}>
        <div>
          <h2 id={headingId} className={cx(styles.planTitle)}>
            {title}
          </h2>
          <p className={cx(styles.muted)}>
            {t("installments.summary", {
              count: plan.count,
              date: formatDate(plan.first_on),
            })}
            {account ? ` · ${account.name}` : ""}
          </p>
        </div>
        {plan.cancelled_at ? (
          <StatusChip tone="neutral" icon="close" label={t("installments.cancelled")} />
        ) : null}
        {isFinished ? (
          <StatusChip tone="ok" icon="check-circle" label={t("installments.finished")} />
        ) : null}
      </div>
      <dl className={cx(styles.figures)}>
        <div className={cx(styles.figure)}>
          <dt>{t("installments.total")}</dt>
          <dd>
            <MoneyAmount amount={plan.total} currency={plan.currency} />
          </dd>
        </div>
        <div className={cx(styles.figure)}>
          <dt>{t("installments.pending")}</dt>
          <dd>
            <MoneyAmount amount={plan.pending} currency={plan.currency} />
          </dd>
        </div>
        <div className={cx(styles.figure)}>
          <dt>{t("installments.progress")}</dt>
          <dd>{t("installments.progressValue", { done: generated, count: plan.count })}</dd>
        </div>
        {next ? (
          <div className={cx(styles.figure)}>
            <dt>{t("installments.next")}</dt>
            {/* Fecha y monto en dos líneas: juntos no entran en un teléfono. */}
            <dd className={cx(styles.stacked)}>
              <span>{formatDate(next.due_on)}</span>
              <MoneyAmount amount={next.amount} currency={plan.currency} />
            </dd>
          </div>
        ) : null}
      </dl>
      <details className={cx(styles.schedule)}>
        <summary>{t("installments.showSchedule")}</summary>
        <TableScroll label={t("installments.scheduleCaption")}>
          <Schedule plan={plan} />
        </TableScroll>
      </details>
      {plan.cancelled_at ? null : (
        <div className={cx(styles.planActions)}>
          <Button
            variant="text"
            onPress={() => {
              setConfirming(true);
            }}
          >
            {t("installments.cancel")}
          </Button>
        </div>
      )}
      <ConfirmDialog
        isOpen={isConfirming}
        onOpenChange={setConfirming}
        title={t("installments.cancelTitle", { name: title })}
        confirmLabel={t("installments.cancelConfirm")}
        cancelLabel={t("installments.cancelKeep")}
        isPending={cancel.isPending}
        onConfirm={() => {
          cancel.mutate(plan.id, {
            onSuccess: () => {
              setConfirming(false);
            },
          });
        }}
      >
        {t("installments.cancelBody")}
      </ConfirmDialog>
    </li>
  );
}

function Schedule({ plan }: { plan: InstallmentPlan }) {
  const { t } = useTranslation();
  const formatDate = useShortDateFormatter();

  function state(item: ScheduledInstallment): string {
    if (item.deleted) return t("installments.state.deleted");
    if (item.transaction_id) return t("installments.state.generated");
    return plan.cancelled_at ? t("installments.state.cancelled") : t("installments.state.pending");
  }

  return (
    <table className={cx(styles.table)}>
      <caption className={cx("visually-hidden")}>{t("installments.scheduleCaption")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("installments.columns.number")}</th>
          <th scope="col">{t("installments.columns.date")}</th>
          <th scope="col" className={cx(styles.number)}>
            {t("installments.columns.amount")}
          </th>
          <th scope="col">{t("installments.columns.state")}</th>
        </tr>
      </thead>
      <tbody>
        {plan.installments.map((item) => (
          <tr key={item.number}>
            {/* Solo el número: la columna ya dice "Cuota", y el total está en la tarjeta. */}
            <th scope="row" className={cx(styles.number)}>
              {item.number}
            </th>
            <td>{formatDate(item.due_on)}</td>
            <td className={cx(styles.number)}>
              <MoneyAmount amount={item.amount} currency={plan.currency} />
            </td>
            <td>{state(item)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
