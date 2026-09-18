import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { useAccounts } from "../accounts/useAccounts";
import styles from "./Transactions.module.css";
import { today } from "./presentation";
import { TransactionForm } from "./TransactionForm";
import { useCategories, useRegisterTransaction } from "./useTransactions";

export function NewTransactionPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  // Solo cuentas activas: en una archivada no se registran movimientos nuevos.
  const accounts = useAccounts(false);
  const categories = useCategories();
  const register = useRegisterTransaction();

  const rows = accounts.data ?? [];
  const preselected = params.get("account") ?? rows[0]?.id ?? "";

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/transactions" variant="text" icon="arrow-back">
          {t("transactions.form.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("transactions.form.titleNew")}</h1>
        <p className={cx(styles.subtitle)}>{t("transactions.form.subtitleNew")}</p>
      </div>
      {accounts.isSuccess && rows.length === 0 ? (
        <section className={cx(styles.empty)} aria-labelledby="no-accounts">
          <h2 id="no-accounts" className={cx(styles.emptyTitle)}>
            {t("transactions.form.noAccountsTitle")}
          </h2>
          <p className={cx(styles.emptyBody)}>{t("transactions.form.noAccountsBody")}</p>
          <LinkButton to="/accounts/new" icon="add">
            {t("transactions.form.noAccountsAction")}
          </LinkButton>
        </section>
      ) : null}
      {rows.length > 0 && categories.isSuccess ? (
        <TransactionForm
          accounts={rows}
          categories={categories.data}
          draft={{
            accountId: preselected,
            kind: "expense",
            amount: "",
            categoryId: "",
            occurredOn: today(),
            description: "",
          }}
          submitLabel={t("transactions.form.submitNew")}
          submittingLabel={t("transactions.form.submitting")}
          isPending={register.isPending}
          error={register.error}
          onSubmit={({ amount, draft }) => {
            register.mutate(
              {
                input: {
                  account_id: draft.accountId,
                  kind: draft.kind,
                  amount,
                  category_id: draft.categoryId,
                  occurred_on: draft.occurredOn,
                  description: draft.description.trim() || null,
                },
                // Una clave por intento de carga: si el pedido se pierde y la
                // persona vuelve a tocar, no se duplica el gasto.
                idempotencyKey: crypto.randomUUID(),
              },
              {
                onSuccess: () => {
                  void navigate("/transactions", {
                    state: withAnnouncement(t("transactions.list.registered")),
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
