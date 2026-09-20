import { useTranslation } from "react-i18next";

import { useShortDateFormatter } from "../../i18n/format";
import { cx } from "../../shared/ui/cx";
import { Icon } from "../../shared/ui/Icon";
import { IconButton } from "../../shared/ui/IconButton";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import type { Account } from "../accounts/api";
import styles from "../transactions/Transactions.module.css";
import type { Transfer } from "./api";

interface TransferRowProps {
  transfer: Transfer;
  accounts: Account[];
  /**
   * Desde qué cuenta se la mira. Sin esto es la vista general, donde la
   * transferencia no suma ni resta: la plata no salió de ningún lado, cambió
   * de lugar (ADR-0014).
   */
  perspective?: string;
  onDelete: (transfer: Transfer) => void;
}

export function TransferRow({ transfer, accounts, perspective, onDelete }: TransferRowProps) {
  const { t } = useTranslation();
  const formatDate = useShortDateFormatter();
  const nameOf = (id: string) => accounts.find((row) => row.id === id)?.name ?? "";

  const isOutgoing = perspective !== undefined && transfer.from_account_id === perspective;
  const isIncoming = perspective !== undefined && transfer.to_account_id === perspective;
  const label =
    isOutgoing || isIncoming
      ? t(isOutgoing ? "transfers.detail.to" : "transfers.detail.from", {
          name: nameOf(isOutgoing ? transfer.to_account_id : transfer.from_account_id),
        })
      : t("transfers.detail.between", {
          from: nameOf(transfer.from_account_id),
          to: nameOf(transfer.to_account_id),
        });
  const name = transfer.description ?? label;

  return (
    <li className={cx(styles.row)}>
      <span className={cx(styles.avatar)}>
        <Icon name={isIncoming ? "movement-in" : isOutgoing ? "movement-out" : "swap"} size={22} />
      </span>
      <span className={cx(styles.text)}>
        <span className={cx(styles.name)}>{name}</span>
        <span className={cx(styles.meta)}>
          {formatDate(transfer.occurred_on)}
          {transfer.description ? ` · ${label}` : ""}
        </span>
      </span>
      <MoneyAmount
        amount={isIncoming ? transfer.received : transfer.sent}
        currency={isIncoming ? transfer.currency_in : transfer.currency_out}
        // Sin perspectiva no lleva signo: vista de conjunto, el patrimonio no cambió.
        tone={isOutgoing ? "expense" : isIncoming ? "income" : "neutral"}
      />
      <span className={cx(styles.rowActions)}>
        <IconButton
          icon="delete"
          label={`${t("transfers.detail.delete")}: ${name}`}
          onPress={() => {
            onDelete(transfer);
          }}
        />
      </span>
    </li>
  );
}
