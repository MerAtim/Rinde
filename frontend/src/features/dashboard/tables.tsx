import { useTranslation } from "react-i18next";

import { useMoneyFormatter, useMonthFormatter } from "../../i18n/format";
import { cx } from "../../shared/ui/cx";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import type { FlowRow, Money, NetWorthPoint } from "./api";
import styles from "./Dashboard.module.css";

/** El patrimonio de cada cierre. Un cierre sin cotización lo dice, no muestra un cero. */
export function NetWorthTable({ points }: { points: NetWorthPoint[] }) {
  const { t } = useTranslation();
  const money = useMoneyFormatter();
  const monthName = useMonthFormatter();

  return (
    <table className={cx(styles.table)}>
      <caption className={cx(styles.caption)}>{t("dashboard.netWorth.caption")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("dashboard.netWorth.month")}</th>
          <th scope="col" className={cx(styles.number)}>
            {t("dashboard.netWorth.total")}
          </th>
        </tr>
      </thead>
      <tbody>
        {points.map((point) => (
          <tr key={point.month}>
            <th scope="row">{monthName(point.month, "long")}</th>
            <td className={cx("numeric", styles.number)}>
              {point.total
                ? money(point.total.amount, point.total.currency)
                : t("dashboard.netWorth.noQuote")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Ingresos, gastos y neto de cada mes. El neto lo calcula el servidor; su signo
 * se lee del string, sin hacer cuentas con el monto. En pesos de hoy, un mes
 * sin IPC lo dice en vez de mostrar un cero (ADR-0025).
 */
export function FlowTable({ monthly }: { monthly: FlowRow[] }) {
  const { t } = useTranslation();
  const monthName = useMonthFormatter();

  return (
    <table className={cx(styles.table)}>
      <caption className={cx(styles.caption)}>{t("dashboard.flow.caption")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("dashboard.flow.month")}</th>
          <th scope="col" className={cx(styles.number)}>
            {t("dashboard.flow.income")}
          </th>
          <th scope="col" className={cx(styles.number)}>
            {t("dashboard.flow.expense")}
          </th>
          <th scope="col" className={cx(styles.number)}>
            {t("dashboard.flow.net")}
          </th>
        </tr>
      </thead>
      <tbody>
        {monthly.map((item) => (
          <tr key={item.month}>
            <th scope="row">{monthName(item.month, "long")}</th>
            <td className={cx(styles.number)}>
              <Cell money={item.income} />
            </td>
            <td className={cx(styles.number)}>
              <Cell money={item.expense} />
            </td>
            <td className={cx(styles.number)}>
              <Cell money={item.net} signed />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Cell({ money, signed = false }: { money: Money | null; signed?: boolean }) {
  const { t } = useTranslation();
  if (!money) {
    return <span className={cx(styles.muted)}>{t("dashboard.flow.noIndex")}</span>;
  }
  return signed ? (
    <SignedAmount amount={money.amount} currency={money.currency} />
  ) : (
    <MoneyAmount amount={money.amount} currency={money.currency} />
  );
}

/**
 * Un neto con signo, flecha y color (WCAG 1.4.1). El servidor manda el signo en
 * el string: "-1500.00" se muestra como gasto de 1500,00.
 */
export function SignedAmount({ amount, currency }: { amount: string; currency: string }) {
  if (amount.startsWith("-")) {
    return <MoneyAmount amount={amount.slice(1)} currency={currency} tone="expense" />;
  }
  const isZero = /^0(\.0+)?$/.test(amount);
  return <MoneyAmount amount={amount} currency={currency} tone={isZero ? "neutral" : "income"} />;
}
