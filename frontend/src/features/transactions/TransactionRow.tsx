import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useShortDateFormatter } from "../../i18n/format";
import { cx } from "../../shared/ui/cx";
import { Icon } from "../../shared/ui/Icon";
import { IconButton } from "../../shared/ui/IconButton";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import type { Account } from "../accounts/api";
import { KIND_ICON } from "../accounts/presentation";
import type { Category, Transaction } from "./api";
import styles from "./Transactions.module.css";
import { useCategoryName } from "./presentation";

interface TransactionRowProps {
  transaction: Transaction;
  categories: Category[];
  accounts: Account[];
  /** En el detalle de una cuenta no hace falta repetir de qué cuenta es. */
  showAccount?: boolean;
  onDelete: (transaction: Transaction) => void;
}

/**
 * Una fila de movimiento: fecha, categoría, cuenta y monto con signo.
 *
 * Vive aparte de la lista porque el historial unificado la intercala con filas
 * de transferencia (ADR-0014), y las dos listas tienen que verse igual.
 */
export function TransactionRow({
  transaction,
  categories,
  accounts,
  showAccount = true,
  onDelete,
}: TransactionRowProps) {
  const { t } = useTranslation();
  const categoryName = useCategoryName();
  const formatDate = useShortDateFormatter();
  const category = categories.find((row) => row.id === transaction.category_id);
  const account = accounts.find((row) => row.id === transaction.account_id);
  const name = transaction.description ?? (category ? categoryName(category) : "");

  return (
    <li className={cx(styles.row)}>
      <span className={cx(styles.avatar)} data-kind={transaction.kind}>
        <Icon name={account ? KIND_ICON[account.kind] : "movements"} size={22} />
      </span>
      <span className={cx(styles.text)}>
        <span className={cx(styles.name)}>{name}</span>
        <span className={cx(styles.meta)}>
          {formatDate(transaction.occurred_on)}
          {category ? ` · ${categoryName(category)}` : ""}
          {showAccount && account ? ` · ${account.name}` : ""}
        </span>
      </span>
      <MoneyAmount
        amount={transaction.amount}
        currency={transaction.currency}
        tone={transaction.kind === "income" ? "income" : "expense"}
      />
      <span className={cx(styles.rowActions)}>
        <Link
          to={`/transactions/${transaction.id}`}
          className={cx("state-layer", styles.iconLink)}
          aria-label={`${t("transactions.list.edit")}: ${name}`}
        >
          <Icon name="edit" size={20} />
        </Link>
        <IconButton
          icon="delete"
          label={`${t("transactions.list.delete")}: ${name}`}
          onPress={() => {
            onDelete(transaction);
          }}
        />
      </span>
    </li>
  );
}
