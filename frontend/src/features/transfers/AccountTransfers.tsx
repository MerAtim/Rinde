import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useShortDateFormatter } from "../../i18n/format";
import { Alert } from "../../shared/ui/Alert";
import { LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { Icon } from "../../shared/ui/Icon";
import { IconButton } from "../../shared/ui/IconButton";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import { Snackbar } from "../../shared/ui/Snackbar";
import type { Account } from "../accounts/api";
import accountStyles from "../accounts/Accounts.module.css";
import styles from "../transactions/Transactions.module.css";
import type { Transfer } from "./api";
import { errorCodeOf } from "./errors";
import {
  flattenTransfers,
  useDeleteTransfer,
  useRestoreTransfer,
  useTransfers,
} from "./useTransfers";

const LATEST = 5;

/**
 * Las transferencias de una cuenta, mirándolas desde esa cuenta: lo que salió
 * es un monto negativo y lo que entró, positivo. La misma fila se ve al revés
 * desde la otra cuenta, y eso es correcto: es una sola operación.
 */
export function AccountTransfers({ account, accounts }: { account: Account; accounts: Account[] }) {
  const { t } = useTranslation();
  const formatDate = useShortDateFormatter();
  const query = useTransfers({ accountId: account.id, limit: LATEST });
  const rows = flattenTransfers(query.data);
  const [undoable, setUndoable] = useState<Transfer | null>(null);
  const remove = useDeleteTransfer();
  const restore = useRestoreTransfer();
  const failure = errorCodeOf(remove.error) ?? errorCodeOf(restore.error);

  const nameOf = (id: string) => accounts.find((row) => row.id === id)?.name ?? "";

  return (
    <section className={cx(accountStyles.section)} aria-labelledby="account-transfers">
      <h2 id="account-transfers" className={cx(accountStyles.sectionTitle)}>
        {t("transfers.detail.title")}
      </h2>
      {failure ? <Alert>{t(`transfers.errors.${failure}`)}</Alert> : null}
      {rows.length > 0 ? (
        <ul className={cx(styles.list)}>
          {rows.map((transfer) => {
            const isOutgoing = transfer.from_account_id === account.id;
            const other = isOutgoing ? transfer.to_account_id : transfer.from_account_id;
            const label = isOutgoing
              ? t("transfers.detail.to", { name: nameOf(other) })
              : t("transfers.detail.from", { name: nameOf(other) });
            return (
              <li key={transfer.id} className={cx(styles.row)}>
                <span className={cx(styles.avatar)}>
                  <Icon name={isOutgoing ? "movement-out" : "movement-in"} size={22} />
                </span>
                <span className={cx(styles.text)}>
                  <span className={cx(styles.name)}>{transfer.description ?? label}</span>
                  <span className={cx(styles.meta)}>
                    {formatDate(transfer.occurred_on)}
                    {transfer.description ? ` · ${label}` : ""}
                  </span>
                </span>
                <MoneyAmount
                  amount={isOutgoing ? transfer.sent : transfer.received}
                  currency={isOutgoing ? transfer.currency_out : transfer.currency_in}
                  tone={isOutgoing ? "expense" : "income"}
                />
                <span className={cx(styles.rowActions)}>
                  <IconButton
                    icon="delete"
                    label={`${t("transfers.detail.delete")}: ${transfer.description ?? label}`}
                    onPress={() => {
                      remove.mutate(transfer.id, {
                        onSuccess: () => {
                          setUndoable(transfer);
                        },
                      });
                    }}
                  />
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
      {query.isSuccess && rows.length === 0 ? (
        <p className={cx(accountStyles.sectionBody)}>{t("transfers.detail.none")}</p>
      ) : null}
      {account.archived_at ? null : (
        <div className={cx(accountStyles.actions)}>
          <LinkButton to={`/transfers/new?account=${account.id}`} icon="swap">
            {t("transfers.detail.add")}
          </LinkButton>
        </div>
      )}
      {undoable ? (
        <Snackbar
          message={t("transfers.deleted")}
          onDismiss={() => {
            setUndoable(null);
          }}
          action={{
            label: t("transfers.detail.undo"),
            onPress: () => {
              restore.mutate(undoable.id);
              setUndoable(null);
            },
          }}
        />
      ) : null}
    </section>
  );
}
