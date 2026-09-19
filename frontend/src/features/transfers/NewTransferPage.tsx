import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router";

import { withAnnouncement } from "../../shared/navigation/announcement";
import { LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { useAccounts } from "../accounts/useAccounts";
import { today } from "../transactions/presentation";
import styles from "../transactions/Transactions.module.css";
import { TransferForm } from "./TransferForm";
import { useRegisterTransfer } from "./useTransfers";

export function NewTransferPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  // Solo cuentas activas: una archivada no envía ni recibe.
  const accounts = useAccounts(false);
  const register = useRegisterTransfer();

  const rows = accounts.data ?? [];
  const from = params.get("account") ?? "";
  // Hacen falta dos cuentas: con una sola no hay a dónde mover la plata.
  const hasEnoughAccounts = rows.length >= 2;

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/accounts" variant="text" icon="arrow-back">
          {t("transfers.form.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("transfers.form.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("transfers.form.subtitle")}</p>
      </div>
      {accounts.isSuccess && !hasEnoughAccounts ? (
        <section className={cx(styles.empty)} aria-labelledby="not-enough-accounts">
          <h2 id="not-enough-accounts" className={cx(styles.emptyTitle)}>
            {t("transfers.form.notEnoughTitle")}
          </h2>
          <p className={cx(styles.emptyBody)}>{t("transfers.form.notEnoughBody")}</p>
          <LinkButton to="/accounts/new" icon="add">
            {t("transfers.form.notEnoughAction")}
          </LinkButton>
        </section>
      ) : null}
      {hasEnoughAccounts ? (
        <TransferForm
          accounts={rows}
          draft={{
            fromAccountId: from,
            toAccountId: "",
            sent: "",
            received: "",
            occurredOn: today(),
            description: "",
          }}
          submitLabel={t("transfers.form.submit")}
          submittingLabel={t("transfers.form.submitting")}
          isPending={register.isPending}
          error={register.error}
          onSubmit={({ sent, received, draft }) => {
            register.mutate(
              {
                input: {
                  from_account_id: draft.fromAccountId,
                  to_account_id: draft.toAccountId,
                  sent,
                  received,
                  occurred_on: draft.occurredOn,
                  description: draft.description.trim() || null,
                },
                // Una clave por intento: si el pedido se pierde y la persona
                // vuelve a tocar, la plata no se mueve dos veces.
                idempotencyKey: crypto.randomUUID(),
              },
              {
                onSuccess: () => {
                  void navigate(from ? `/accounts/${from}` : "/accounts", {
                    state: withAnnouncement(t("transfers.registered")),
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
