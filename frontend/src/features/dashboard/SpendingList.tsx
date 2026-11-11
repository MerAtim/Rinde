import { useId } from "react";
import { useTranslation } from "react-i18next";

import { cx } from "../../shared/ui/cx";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import { useCategoryName } from "../transactions/presentation";
import type { CategorySpending } from "./api";
import { barWidths } from "./charts/series";
import styles from "./Dashboard.module.css";

/**
 * Gastos por categoría, de mayor a menor, como barras horizontales con un solo
 * tono. Es una tabla de verdad: el nombre y el monto están escritos en cada
 * fila, así que la misma pieza es el gráfico y su versión accesible. Las barras
 * son decorativas para el lector de pantalla.
 */
export function SpendingList({ spending }: { spending: CategorySpending[] }) {
  const { t } = useTranslation();
  const headingId = useId();
  const categoryName = useCategoryName();
  const widths = barWidths(spending);

  return (
    <section aria-labelledby={headingId} className={cx(styles.card)}>
      <h2 id={headingId} className={cx(styles.cardTitle)}>
        {t("dashboard.spending.heading")}
      </h2>
      {spending.length === 0 ? (
        <p className={cx(styles.muted)}>{t("dashboard.spending.none")}</p>
      ) : (
        <table className={cx(styles.table, styles.spending)}>
          <caption className={cx("visually-hidden")}>{t("dashboard.spending.caption")}</caption>
          <thead className={cx("visually-hidden")}>
            <tr>
              <th scope="col">{t("dashboard.spending.category")}</th>
              <th scope="col">{t("dashboard.spending.total")}</th>
            </tr>
          </thead>
          <tbody>
            {spending.map((item, index) => (
              <tr key={item.category.id}>
                <th scope="row">
                  <span className={cx(styles.spendingName)}>{categoryName(item.category)}</span>
                  <span className={cx(styles.track)} aria-hidden="true">
                    <span
                      className={cx(styles.bar)}
                      style={{ inlineSize: `${String(widths[index] ?? 0)}%` }}
                    />
                  </span>
                </th>
                <td className={cx(styles.number)}>
                  <MoneyAmount amount={item.total.amount} currency={item.total.currency} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
