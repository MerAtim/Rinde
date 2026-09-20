import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { useAccounts } from "../accounts/useAccounts";
import { errorCodeOf } from "./errors";
import { HistoryFilters, type HistoryFilterValues } from "./HistoryFilters";
import { HistoryWithUndo } from "./HistoryList";
import styles from "./Transactions.module.css";
import { flattenHistory, useCategories, useHistory } from "./useTransactions";

export function TransactionsPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  // Se puede llegar desde una cuenta: entonces la lista viene acotada a esa cuenta.
  const accountId = params.get("account") ?? undefined;
  // Los filtros viven en la URL: se pueden compartir y sobreviven a recargar.
  const filters: HistoryFilterValues = {
    categoryId: params.get("category") ?? "",
    text: params.get("q") ?? "",
  };
  const history = useHistory({
    ...(accountId ? { accountId } : {}),
    ...(filters.categoryId ? { categoryId: filters.categoryId } : {}),
    ...(filters.text ? { text: filters.text } : {}),
  });
  const categories = useCategories();
  // Las archivadas también, para poder mostrar de qué cuenta es cada fila.
  const accounts = useAccounts(true);
  const rows = flattenHistory(history.data);
  const hasFilters = filters.categoryId !== "" || filters.text !== "";

  return (
    <div className={cx(styles.page)}>
      <header className={cx(styles.header)}>
        <div className={cx(styles.heading)}>
          <h1 className={cx(styles.title)}>{t("transactions.list.title")}</h1>
          <p className={cx(styles.subtitle)}>{t("transactions.list.subtitle")}</p>
        </div>
        {rows.length > 0 || hasFilters ? (
          <LinkButton to="/transactions/new" icon="add">
            {t("transactions.list.add")}
          </LinkButton>
        ) : null}
      </header>
      {categories.isSuccess && (categories.data.length > 0 || hasFilters) ? (
        <HistoryFilters
          categories={categories.data}
          values={filters}
          onChange={(next) => {
            const updated = new URLSearchParams(params);
            const cambios: [string, string][] = [
              ["category", next.categoryId],
              ["q", next.text],
            ];
            for (const [clave, valor] of cambios) {
              if (valor) {
                updated.set(clave, valor);
              } else {
                updated.delete(clave);
              }
            }
            setParams(updated, { replace: true });
          }}
        />
      ) : null}
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
            {hasFilters ? t("transactions.filters.noneTitle") : t("transactions.list.emptyTitle")}
          </h2>
          <p className={cx(styles.emptyBody)}>
            {hasFilters ? t("transactions.filters.noneBody") : t("transactions.list.emptyBody")}
          </p>
          {hasFilters ? null : (
            <LinkButton to="/transactions/new" icon="add">
              {t("transactions.list.emptyAction")}
            </LinkButton>
          )}
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
