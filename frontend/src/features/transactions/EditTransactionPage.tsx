import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { useAccounts } from "../accounts/useAccounts";
import { fetchTransaction, isTransactionsApiError } from "./api";
import { errorCodeOf } from "./errors";
import styles from "./Transactions.module.css";
import { TransactionForm } from "./TransactionForm";
import { transactionKeys, useCategories, useEditTransaction } from "./useTransactions";

/** Un movimiento ajeno, inexistente o borrado se informa igual: no encontrado. */
function isNotFound(error: unknown): boolean {
  return isTransactionsApiError(error) && (error.status === 404 || error.status === 422);
}

export function EditTransactionPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { transactionId = "" } = useParams();
  const transaction = useQuery({
    queryKey: [...transactionKeys.all, "detail", transactionId],
    queryFn: ({ signal }) => fetchTransaction(transactionId, signal),
  });
  const accounts = useAccounts(true);
  const categories = useCategories();
  const edit = useEditTransaction(transactionId);

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/transactions" variant="text" icon="arrow-back">
          {t("transactions.form.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("transactions.form.titleEdit")}</h1>
        <p className={cx(styles.subtitle)}>{t("transactions.form.subtitleEdit")}</p>
      </div>
      {transaction.isPending ? (
        <p role="status" className={cx(styles.subtitle)}>
          {t("transactions.list.loading")}
        </p>
      ) : null}
      {transaction.isError ? (
        <Alert>
          {t(
            `transactions.errors.${
              isNotFound(transaction.error)
                ? "TRANSACTION_NOT_FOUND"
                : (errorCodeOf(transaction.error) ?? "UNKNOWN_ERROR")
            }`,
          )}
        </Alert>
      ) : null}
      {transaction.isSuccess && categories.isSuccess ? (
        <TransactionForm
          accounts={accounts.data ?? []}
          categories={categories.data}
          isAccountFixed
          draft={{
            accountId: transaction.data.account_id,
            kind: transaction.data.kind,
            amount: transaction.data.amount,
            categoryId: transaction.data.category_id,
            occurredOn: transaction.data.occurred_on,
            description: transaction.data.description ?? "",
          }}
          submitLabel={t("transactions.form.submitEdit")}
          submittingLabel={t("transactions.form.submitting")}
          isPending={edit.isPending}
          error={edit.error}
          onSubmit={({ amount, draft }) => {
            edit.mutate(
              {
                kind: draft.kind,
                amount,
                category_id: draft.categoryId,
                occurred_on: draft.occurredOn,
                description: draft.description.trim() || null,
              },
              {
                onSuccess: () => {
                  void navigate("/transactions", {
                    state: withAnnouncement(t("transactions.list.saved")),
                  });
                },
              },
            );
          }}
        />
      ) : null}
    </div>
  );
}
