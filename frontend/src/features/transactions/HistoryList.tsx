import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Alert } from "../../shared/ui/Alert";
import { cx } from "../../shared/ui/cx";
import { Snackbar } from "../../shared/ui/Snackbar";
import type { Account } from "../accounts/api";
import { TransferRow } from "../transfers/TransferRow";
import { errorCodeOf as transferErrorCodeOf } from "../transfers/errors";
import { useDeleteTransfer, useRestoreTransfer } from "../transfers/useTransfers";
import type { Category, HistoryEntry } from "./api";
import { errorCodeOf } from "./errors";
import styles from "./Transactions.module.css";
import { TransactionRow } from "./TransactionRow";
import { useDeleteTransaction, useRestoreTransaction } from "./useTransactions";

interface HistoryListProps {
  entries: HistoryEntry[];
  categories: Category[];
  accounts: Account[];
  /** En el detalle de una cuenta no hace falta repetir de qué cuenta es. */
  showAccount?: boolean;
  /** Desde qué cuenta se miran las transferencias, si se mira desde una. */
  perspective?: string;
}

/** Lo que se puede deshacer después de borrar, sin importar de qué tipo era. */
interface Undoable {
  message: string;
  restore: () => void;
}

/**
 * Movimientos y transferencias en una sola lista (ADR-0014).
 *
 * Borrar no pregunta: borra y ofrece deshacer durante seis segundos. El aviso
 * vive acá, fuera de la lista: al borrar la última fila la lista queda vacía, y
 * si el aviso viviera dentro se iría con ella justo cuando hace falta.
 */
export function HistoryWithUndo({
  entries,
  categories,
  accounts,
  showAccount = true,
  perspective,
}: HistoryListProps) {
  const { t } = useTranslation();
  const [undoable, setUndoable] = useState<Undoable | null>(null);
  const removeTransaction = useDeleteTransaction();
  const restoreTransaction = useRestoreTransaction();
  const removeTransfer = useDeleteTransfer();
  const restoreTransfer = useRestoreTransfer();

  const transactionFailure =
    errorCodeOf(removeTransaction.error) ?? errorCodeOf(restoreTransaction.error);
  const transferFailure =
    transferErrorCodeOf(removeTransfer.error) ?? transferErrorCodeOf(restoreTransfer.error);

  return (
    <>
      {transactionFailure ? <Alert>{t(`transactions.errors.${transactionFailure}`)}</Alert> : null}
      {transferFailure ? <Alert>{t(`transfers.errors.${transferFailure}`)}</Alert> : null}
      {entries.length > 0 ? (
        <ul className={cx(styles.list)}>
          {entries.map((entry) =>
            entry.type === "transfer" ? (
              <TransferRow
                key={entry.transfer.id}
                transfer={entry.transfer}
                accounts={accounts}
                {...(perspective === undefined ? {} : { perspective })}
                onDelete={(transfer) => {
                  removeTransfer.mutate(transfer.id, {
                    onSuccess: () => {
                      setUndoable({
                        message: t("transfers.deleted"),
                        restore: () => {
                          restoreTransfer.mutate(transfer.id);
                        },
                      });
                    },
                  });
                }}
              />
            ) : (
              <TransactionRow
                key={entry.transaction.id}
                transaction={entry.transaction}
                categories={categories}
                accounts={accounts}
                showAccount={showAccount}
                onDelete={(transaction) => {
                  removeTransaction.mutate(transaction.id, {
                    onSuccess: () => {
                      setUndoable({
                        message: t("transactions.list.deleted"),
                        restore: () => {
                          restoreTransaction.mutate(transaction.id);
                        },
                      });
                    },
                  });
                }}
              />
            ),
          )}
        </ul>
      ) : null}
      {undoable ? (
        <Snackbar
          message={undoable.message}
          onDismiss={() => {
            setUndoable(null);
          }}
          action={{
            label: t("transactions.list.undo"),
            onPress: () => {
              undoable.restore();
              setUndoable(null);
            },
          }}
        />
      ) : null}
    </>
  );
}
