import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useDateTimeFormatter, useMoneyFormatter, useMonthFormatter } from "../../i18n/format";
import { argentineMonth } from "../../shared/time/argentina";
import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { StatusChip } from "../../shared/ui/StatusChip";
import { useCategoryName } from "../transactions/presentation";
import type { BudgetAlert } from "./api";
import styles from "./Alerts.module.css";
import { THRESHOLD } from "./presentation";
import { useAlerts, useMarkAlertsRead } from "./useAlerts";

/** Los avisos de presupuesto, de la más nueva a la más vieja (ADR-0022). */
export function AlertsPage() {
  const { t } = useTranslation();
  const alerts = useAlerts();
  const markRead = useMarkAlertsRead();
  const heading = useRef<HTMLHeadingElement>(null);
  const unread = alerts.data?.alerts.filter((alert) => !alert.read) ?? [];

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.header)}>
        <div className={cx(styles.heading)}>
          {/* Recibe el foco al marcar como leídas: el botón desaparece. */}
          <h1 ref={heading} tabIndex={-1} className={cx(styles.title)}>
            {t("alerts.title")}
          </h1>
          <p className={cx(styles.subtitle)}>{t("alerts.subtitle")}</p>
        </div>
        {unread.length > 0 ? (
          <Button
            variant="tonal"
            icon="check"
            isDisabled={markRead.isPending}
            onPress={() => {
              markRead.mutate(
                unread.map((alert) => alert.id),
                {
                  onSuccess: () => {
                    heading.current?.focus();
                  },
                },
              );
            }}
          >
            {t("alerts.markRead")}
          </Button>
        ) : null}
      </div>
      {markRead.isError ? <Alert>{t("alerts.markReadError")}</Alert> : null}
      {alerts.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("alerts.loading")}
        </p>
      ) : null}
      {alerts.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>{t("alerts.loadError")}</Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void alerts.refetch();
            }}
          >
            {t("alerts.retry")}
          </Button>
        </div>
      ) : null}
      {alerts.isSuccess && alerts.data.alerts.length === 0 ? (
        <div className={cx(styles.empty)}>
          <p className={cx(styles.emptyTitle)}>{t("alerts.empty.title")}</p>
          <p className={cx(styles.muted)}>{t("alerts.empty.body")}</p>
        </div>
      ) : null}
      {alerts.isSuccess && alerts.data.alerts.length > 0 ? (
        <ul className={cx(styles.list)}>
          {alerts.data.alerts.map((alert) => (
            <AlertRow key={alert.id} alert={alert} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function AlertRow({ alert }: { alert: BudgetAlert }) {
  const { t } = useTranslation();
  const money = useMoneyFormatter();
  const formatMonth = useMonthFormatter();
  const formatMoment = useDateTimeFormatter();
  const categoryName = useCategoryName();
  const threshold = THRESHOLD[alert.threshold];
  const month = formatMonth(alert.month, "long");
  // El mes en curso no va en la URL de presupuestos (ADR-0020).
  const budgetsLink =
    alert.month >= argentineMonth(new Date())
      ? "/budgets"
      : `/budgets?${new URLSearchParams({ month: alert.month }).toString()}`;

  return (
    <li className={cx(styles.row)} data-unread={!alert.read || undefined}>
      <div className={cx(styles.rowHeader)}>
        <div className={cx(styles.text)}>
          <p className={cx(styles.name)}>
            {t(`alerts.message.${alert.threshold}`, { name: categoryName(alert.category) })}
          </p>
          <p className={cx(styles.meta)}>{formatMoment(alert.raised_at)}</p>
        </div>
        {/* Sin leer se dice con texto, no solo con el punto de color. */}
        {alert.read ? null : <span className={cx(styles.unread)}>{t("alerts.unread")}</span>}
        <StatusChip
          tone={threshold.tone}
          icon={threshold.icon}
          label={t(`alerts.threshold.${alert.threshold}`)}
        />
      </div>
      <p className={cx(styles.detail)}>
        {t("alerts.detail", {
          spent: money(alert.spent.amount, alert.spent.currency),
          limit: money(alert.limit.amount, alert.limit.currency),
          month,
        })}
      </p>
      <Link className={cx(styles.link)} to={budgetsLink}>
        {t("alerts.viewBudgets", { month })}
      </Link>
    </li>
  );
}
