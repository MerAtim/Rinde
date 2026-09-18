import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { Snackbar } from "../../shared/ui/Snackbar";
import { useAccounts } from "../accounts/useAccounts";
import type { Account } from "../accounts/api";
import type { Category, Transaction } from "./api";
import { errorCodeOf } from "./errors";
import styles from "./Transactions.module.css";
import { TransactionList } from "./TransactionList";
import {
  flatten,
  useCategories,
  useDeleteTransaction,
  useRestoreTransaction,
  useTransactions,
} from "./useTransactions";

export function TransactionsPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  // Se puede llegar desde una cuenta: entonces la lista viene acotada a esa cuenta.
  const accountId = params.get("account") ?? undefined;
  const transactions = useTransactions(accountId ? { accountId } : {});
  const categories = useCategories();
  // Las archivadas también, para poder mostrar de qué cuenta es cada movimiento.
  const accounts = useAccounts(true);
  const rows = flatten(transactions.data);

  return (
    <div className={cx(styles.page)}>
      <header className={cx(styles.header)}>
        <div className={cx(styles.heading)}>
          <h1 className={cx(styles.title)}>{t("transactions.list.title")}</h1>
          <p className={cx(styles.subtitle)}>{t("transactions.list.subtitle")}</p>
        </div>
        {rows.length > 0 ? (
          <LinkButton to="/transactions/new" icon="add">
            {t("transactions.list.add")}
          </LinkButton>
        ) : null}
      </header>
      {transactions.isPending ? (
        <p role="status" className={cx(styles.subtitle)}>
          {t("transactions.list.loading")}
        </p>
      ) : null}
      {transactions.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>
            {t(`transactions.errors.${errorCodeOf(transactions.error) ?? "UNKNOWN_ERROR"}`)}
          </Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void transactions.refetch();
            }}
          >
            {t("transactions.list.retry")}
          </Button>
        </div>
      ) : null}
      {transactions.isSuccess && rows.length === 0 ? (
        <section className={cx(styles.empty)} aria-labelledby="transactions-empty">
          <h2 id="transactions-empty" className={cx(styles.emptyTitle)}>
            {t("transactions.list.emptyTitle")}
          </h2>
          <p className={cx(styles.emptyBody)}>{t("transactions.list.emptyBody")}</p>
          <LinkButton to="/transactions/new" icon="add">
            {t("transactions.list.emptyAction")}
          </LinkButton>
        </section>
      ) : null}
      <TransactionsWithUndo
        transactions={rows}
        categories={categories.data ?? []}
        accounts={accounts.data ?? []}
      />
      {transactions.hasNextPage ? (
        <Button
          variant="outlined"
          isDisabled={transactions.isFetchingNextPage}
          onPress={() => {
            void transactions.fetchNextPage();
          }}
        >
          {transactions.isFetchingNextPage
            ? t("transactions.list.loadingMore")
            : t("transactions.list.more")}
        </Button>
      ) : null}
    </div>
  );
}

interface WithUndoProps {
  transactions: Transaction[];
  categories: Category[];
  accounts: Account[];
  /** En el detalle de una cuenta no hace falta repetir de qué cuenta es cada uno. */
  showAccount?: boolean;
}

/**
 * Borrar no pregunta: borra y ofrece deshacer durante seis segundos, que es lo
 * que prefiere el sistema de diseño frente a un diálogo de confirmación.
 *
 * El aviso vive acá, fuera de la lista: al borrar el último movimiento la lista
 * queda vacía, y si el aviso viviera dentro se iría con ella justo cuando hace
 * falta.
 */
export function TransactionsWithUndo({
  transactions,
  categories,
  accounts,
  showAccount = true,
}: WithUndoProps) {
  const { t } = useTranslation();
  const [undoable, setUndoable] = useState<Transaction | null>(null);
  const remove = useDeleteTransaction();
  const restore = useRestoreTransaction();
  const failure = errorCodeOf(remove.error) ?? errorCodeOf(restore.error);

  return (
    <>
      {failure ? <Alert>{t(`transactions.errors.${failure}`)}</Alert> : null}
      {transactions.length > 0 ? (
        <TransactionList
          transactions={transactions}
          categories={categories}
          accounts={accounts}
          showAccount={showAccount}
          onDelete={(transaction) => {
            remove.mutate(transaction.id, {
              onSuccess: () => {
                setUndoable(transaction);
              },
            });
          }}
        />
      ) : null}
      {undoable ? (
        <Snackbar
          message={t("transactions.list.deleted")}
          onDismiss={() => {
            setUndoable(null);
          }}
          action={{
            label: t("transactions.list.undo"),
            onPress: () => {
              restore.mutate(undoable.id);
              setUndoable(null);
            },
          }}
        />
      ) : null}
    </>
  );
}
