import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { useAccounts } from "../accounts/useAccounts";
import { errorCodeOf } from "./errors";
import { HistoryWithUndo } from "./HistoryList";
import styles from "./Transactions.module.css";
import { flattenHistory, useCategories, useHistory } from "./useTransactions";

export function TransactionsPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  // Se puede llegar desde una cuenta: entonces la lista viene acotada a esa cuenta.
  const accountId = params.get("account") ?? undefined;
  const history = useHistory(accountId ? { accountId } : {});
  const categories = useCategories();
  // Las archivadas también, para poder mostrar de qué cuenta es cada fila.
  const accounts = useAccounts(true);
  const rows = flattenHistory(history.data);

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
      {history.isPending ? (
        <p role="status" className={cx(styles.subtitle)}>
          {t("transactions.list.loading")}
        </p>
      ) : null}
      {history.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>{t(`transactions.errors.${errorCodeOf(history.error) ?? "UNKNOWN_ERROR"}`)}</Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void history.refetch();
            }}
          >
            {t("transactions.list.retry")}
          </Button>
        </div>
      ) : null}
      {history.isSuccess && rows.length === 0 ? (
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
      <HistoryWithUndo
        entries={rows}
        categories={categories.data ?? []}
        accounts={accounts.data ?? []}
      />
      {history.hasNextPage ? (
        <Button
          variant="outlined"
          isDisabled={history.isFetchingNextPage}
          onPress={() => {
            void history.fetchNextPage();
          }}
        >
          {history.isFetchingNextPage
            ? t("transactions.list.loadingMore")
            : t("transactions.list.more")}
        </Button>
      ) : null}
    </div>
  );
}
