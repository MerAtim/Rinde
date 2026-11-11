import { useTranslation } from "react-i18next";

import { cx } from "../../shared/ui/cx";
import { Select } from "../../shared/ui/Select";
import type { Account } from "../accounts/api";
import styles from "./Dashboard.module.css";
import { type DashboardFilters as Filters, PERIOD_MONTHS, type PeriodMonths } from "./period";

interface DashboardFiltersProps {
  accounts: Account[];
  values: Filters;
  onChange: (values: Filters) => void;
}

/**
 * Una sola fila de filtros, arriba de todo lo que acota: los tres bloques del
 * resumen muestran siempre el mismo período y las mismas cuentas.
 */
export function DashboardFilters({ accounts, values, onChange }: DashboardFiltersProps) {
  const { t } = useTranslation();

  return (
    <div role="group" aria-label={t("dashboard.filters.label")} className={cx(styles.filters)}>
      <Select
        label={t("dashboard.filters.period")}
        placeholder={t("dashboard.filters.months", { count: values.months })}
        options={PERIOD_MONTHS.map((months) => ({
          id: String(months),
          label: t("dashboard.filters.months", { count: months }),
        }))}
        value={String(values.months)}
        onChange={(months) => {
          const chosen = PERIOD_MONTHS.find((option) => String(option) === months);
          if (chosen !== undefined) {
            onChange({ ...values, months: chosen satisfies PeriodMonths });
          }
        }}
      />
      <Select
        label={t("dashboard.filters.account")}
        placeholder={t("dashboard.filters.allAccounts")}
        options={[
          { id: "", label: t("dashboard.filters.allAccounts") },
          ...accounts.map((account) => ({
            id: account.id,
            label: account.archived_at
              ? t("dashboard.filters.archived", { name: account.name })
              : account.name,
          })),
        ]}
        value={values.accountId}
        onChange={(accountId) => {
          onChange({ ...values, accountId });
        }}
      />
    </div>
  );
}
