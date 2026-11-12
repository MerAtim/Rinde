import { type ReactNode, useState } from "react";
import { Label, Meter } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { useLocation, useSearchParams } from "react-router";

import { useLocale, useMonthFormatter, useMoneyFormatter } from "../../i18n/format";
import { announcementFrom } from "../../shared/navigation/announcement";
import { argentineMonth } from "../../shared/time/argentina";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { IconButton, LinkIconButton } from "../../shared/ui/IconButton";
import { Snackbar } from "../../shared/ui/Snackbar";
import { StatusChip, type StatusTone } from "../../shared/ui/StatusChip";
import type { IconName } from "../../shared/ui/Icon";
import { useCategoryName } from "../transactions/presentation";
import type { Budget, BudgetMonth, BudgetStatus } from "./api";
import styles from "./Budgets.module.css";
import { monthFrom, shiftMonth, withMonth } from "./month";
import { useBudgets, useRemoveBudget, useSetBudget } from "./useBudgets";

const STATUS: Record<BudgetStatus, { tone: StatusTone; icon: IconName }> = {
  on_track: { tone: "ok", icon: "check-circle" },
  warning: { tone: "warning", icon: "warning" },
  over: { tone: "error", icon: "error" },
};

/** Cuánto se gastó de cada tope en un mes (ADR-0021). El mes vive en la URL. */
export function BudgetsPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const current = argentineMonth(new Date());
  const month = monthFrom(params, current);
  const shown = month ?? current;
  const isCurrent = month === null;
  const budgets = useBudgets(month);
  const formatMonth = useMonthFormatter();
  const announcement = announcementFrom(location.state);

  function go(delta: number) {
    setParams(withMonth(params, shiftMonth(shown, delta), current));
  }

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.header)}>
        <div className={cx(styles.heading)}>
          <h1 className={cx(styles.title)}>{t("budgets.title")}</h1>
          <p className={cx(styles.subtitle)}>{t("budgets.subtitle")}</p>
        </div>
        {isCurrent ? (
          <LinkButton to="/budgets/new" icon="add">
            {t("budgets.new")}
          </LinkButton>
        ) : null}
      </div>
      <div role="group" aria-label={t("budgets.month.label")} className={cx(styles.months)}>
        <IconButton
          icon="chevron-left"
          label={t("budgets.month.previous")}
          onPress={() => {
            go(-1);
          }}
        />
        <p className={cx(styles.month)} aria-live="polite">
          {formatMonth(shown, "long")}
        </p>
        <IconButton
          icon="chevron-right"
          label={t("budgets.month.next")}
          isDisabled={isCurrent}
          onPress={() => {
            go(1);
          }}
        />
      </div>
      {announcement ? (
        <p role="status" className={cx(styles.announcement)}>
          {announcement}
        </p>
      ) : null}
      {isCurrent ? null : <p className={cx(styles.muted)}>{t("budgets.pastNote")}</p>}
      {budgets.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("budgets.loading")}
        </p>
      ) : null}
      {budgets.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>{t("budgets.loadError")}</Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void budgets.refetch();
            }}
          >
            {t("budgets.retry")}
          </Button>
        </div>
      ) : null}
      {budgets.isSuccess ? (
        <BudgetList
          budgets={budgets.data.budgets}
          rateType={budgets.data.rate_type}
          isCurrent={isCurrent}
          isUpdating={budgets.isPlaceholderData}
        />
      ) : null}
    </div>
  );
}

interface BudgetListProps {
  budgets: Budget[];
  rateType: BudgetMonth["rate_type"];
  isCurrent: boolean;
  isUpdating: boolean;
}

function BudgetList({ budgets, rateType, isCurrent, isUpdating }: BudgetListProps) {
  const { t } = useTranslation();
  const locale = useLocale();
  const categoryName = useCategoryName();
  const remove = useRemoveBudget();
  const restore = useSetBudget();
  const [undoable, setUndoable] = useState<Budget | null>(null);

  if (budgets.length === 0) {
    return (
      <div className={cx(styles.empty)}>
        <p className={cx(styles.emptyTitle)}>
          {isCurrent ? t("budgets.empty.title") : t("budgets.empty.pastTitle")}
        </p>
        {isCurrent ? <p className={cx(styles.muted)}>{t("budgets.empty.body")}</p> : null}
      </div>
    );
  }

  // El servidor ordena por el nombre guardado; acá se ordena por el que se ve,
  // que en las categorías sembradas es la traducción.
  const collator = new Intl.Collator(locale);
  const sorted = budgets
    .map((budget) => ({ budget, name: categoryName(budget.category) }))
    .sort((a, b) => collator.compare(a.name, b.name));

  return (
    <>
      {remove.isError ? <Alert>{t("budgets.removeError")}</Alert> : null}
      <p className={cx(styles.muted)}>
        {/* El nombre del dólar en minúscula, para ir dentro de una frase, como en el resumen. */}
        {t("budgets.conversion", { rate: t(`dashboard.rate.${rateType}`) })}
      </p>
      <ul
        className={cx(styles.list)}
        aria-busy={isUpdating}
        data-updating={isUpdating || undefined}
      >
        {sorted.map(({ budget, name }) => (
          <BudgetRow
            key={budget.category.id}
            budget={budget}
            name={name}
            actions={
              isCurrent ? (
                <div className={cx(styles.actions)}>
                  <LinkIconButton
                    to={`/budgets/${budget.category.id}/edit`}
                    icon="edit"
                    label={t("budgets.edit", { name })}
                  />
                  <IconButton
                    icon="delete"
                    label={t("budgets.remove", { name })}
                    isDisabled={remove.isPending}
                    onPress={() => {
                      remove.mutate(budget.category.id, {
                        onSuccess: () => {
                          setUndoable(budget);
                        },
                      });
                    }}
                  />
                </div>
              ) : null
            }
          />
        ))}
      </ul>
      {undoable ? (
        <Snackbar
          message={t("budgets.removed", { name: categoryName(undoable.category) })}
          onDismiss={() => {
            setUndoable(null);
          }}
          action={{
            label: t("budgets.undo"),
            onPress: () => {
              // Deshacer es volver a fijar el mismo tope: queda una vigencia más.
              restore.mutate({
                categoryId: undoable.category.id,
                input: { amount: undoable.limit.amount, currency: undoable.limit.currency },
              });
              setUndoable(null);
            },
          }}
        />
      ) : null}
    </>
  );
}

interface BudgetRowProps {
  budget: Budget;
  name: string;
  actions: ReactNode;
}

function BudgetRow({ budget, name, actions }: BudgetRowProps) {
  const { t } = useTranslation();
  const locale = useLocale();
  const money = useMoneyFormatter();
  const formatMonth = useMonthFormatter();
  const status = STATUS[budget.status];
  // La proporción no es dinero: solo ubica la barra y se lee como porcentaje.
  const ratio = Number(budget.ratio);
  const percent = new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(ratio);
  // El signo se lee del string: restar en el frontend sería aritmética de dinero.
  const isOver = budget.remaining.amount.startsWith("-");
  const remaining = money(budget.remaining.amount.replace(/^-/, ""), budget.remaining.currency);

  return (
    <li className={cx(styles.row)}>
      <div className={cx(styles.rowHeader)}>
        <div className={cx(styles.text)}>
          <p className={cx(styles.name)}>{name}</p>
          <p className={cx(styles.meta)}>
            {t("budgets.since", { month: formatMonth(budget.since, "long") })}
          </p>
        </div>
        <StatusChip
          tone={status.tone}
          icon={status.icon}
          label={t(`budgets.status.${budget.status}`)}
        />
        {actions}
      </div>
      <Meter
        className={cx(styles.meter)}
        value={Math.min(ratio, 1) * 100}
        valueLabel={t("budgets.meter", { percent })}
        data-status={budget.status}
      >
        <Label className={cx(styles.meterLabel)}>
          {t("budgets.spentOf", {
            spent: money(budget.spent.amount, budget.spent.currency),
            limit: money(budget.limit.amount, budget.limit.currency),
          })}
        </Label>
        <span className={cx(styles.track)} aria-hidden="true">
          <span
            className={cx(styles.bar)}
            style={{ inlineSize: `${String(Math.min(ratio, 1) * 100)}%` }}
          />
        </span>
      </Meter>
      <p className={cx(styles.remaining)} data-over={isOver || undefined}>
        {isOver
          ? t("budgets.exceeded", { amount: remaining })
          : t("budgets.remaining", { amount: remaining })}
        <span className={cx(styles.percent)}>{t("budgets.meter", { percent })}</span>
      </p>
      {budget.unconverted.length > 0 ? (
        <p className={cx(styles.meta)}>
          {t("budgets.unconverted", {
            amounts: budget.unconverted.map((item) => money(item.amount, item.currency)).join(", "),
          })}
        </p>
      ) : null}
    </li>
  );
}
