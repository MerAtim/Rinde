import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { Checkbox } from "../../shared/ui/Checkbox";
import { cx } from "../../shared/ui/cx";
import { Icon } from "../../shared/ui/Icon";
import { StatusChip } from "../../shared/ui/StatusChip";
import styles from "./Accounts.module.css";
import type { Account } from "./api";
import { KIND_ICON } from "./presentation";
import { useAccounts } from "./useAccounts";

// El filtro vive en la URL: sobrevive a recargar, se comparte y respeta el botón Atrás.
const ARCHIVED_PARAM = "archived";

export function AccountsPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const includeArchived = params.get(ARCHIVED_PARAM) === "1";
  const accounts = useAccounts(includeArchived);
  const isEmpty = accounts.isSuccess && accounts.data.length === 0;

  return (
    <div className={cx(styles.page)}>
      <header className={cx(styles.header)}>
        <div className={cx(styles.heading)}>
          <h1 className={cx(styles.title)}>{t("accounts.list.title")}</h1>
          <p className={cx(styles.subtitle)}>{t("accounts.list.subtitle")}</p>
        </div>
        {/* Una sola acción rellena por pantalla: si la lista está vacía, la ofrece el estado vacío. */}
        {isEmpty ? null : (
          <LinkButton to="/accounts/new" icon="add">
            {t("accounts.list.open")}
          </LinkButton>
        )}
      </header>
      <Checkbox
        isSelected={includeArchived}
        onChange={(selected) => {
          setParams(selected ? { [ARCHIVED_PARAM]: "1" } : {}, { replace: true });
        }}
      >
        {t("accounts.list.showArchived")}
      </Checkbox>
      {accounts.isPending ? <AccountsSkeleton /> : null}
      {accounts.isError ? (
        <div className={cx(styles.problem)}>
          <Alert>{t("accounts.list.error")}</Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void accounts.refetch();
            }}
          >
            {t("accounts.list.retry")}
          </Button>
        </div>
      ) : null}
      {isEmpty ? (
        <section className={cx(styles.empty)} aria-labelledby="accounts-empty-title">
          <h2 id="accounts-empty-title" className={cx(styles.emptyTitle)}>
            {t("accounts.list.emptyTitle")}
          </h2>
          <p className={cx(styles.emptyBody)}>{t("accounts.list.emptyBody")}</p>
          <LinkButton to="/accounts/new" icon="add">
            {t("accounts.list.emptyAction")}
          </LinkButton>
        </section>
      ) : null}
      {accounts.isSuccess && !isEmpty ? (
        <ul className={cx(styles.list)}>
          {accounts.data.map((account) => (
            <li key={account.id}>
              <AccountRow account={account} />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function AccountRow({ account }: { account: Account }) {
  const { t } = useTranslation();

  // Sin saldo por ahora: se calcula con los movimientos (ADR-0009), que todavía no existen.
  return (
    <Link to={`/accounts/${account.id}`} className={cx("state-layer", styles.row)}>
      <span className={cx(styles.avatar)}>
        <Icon name={KIND_ICON[account.kind]} size={24} />
      </span>
      <span className={cx(styles.text)}>
        <span className={cx(styles.name)}>{account.name}</span>
        <span className={cx(styles.meta)}>
          {t(`accounts.kind.${account.kind}`)}
          {account.archived_at ? (
            <StatusChip tone="neutral" icon="archive" label={t("accounts.list.archived")} />
          ) : null}
        </span>
      </span>
      <span className={cx(styles.currency)}>
        <span aria-hidden="true">{account.currency}</span>
        <span className="visually-hidden">{t(`accounts.currency.${account.currency}`)}</span>
      </span>
      <span className={cx(styles.chevron)}>
        <Icon name="chevron-right" size={24} />
      </span>
    </Link>
  );
}

function AccountsSkeleton() {
  const { t } = useTranslation();
  return (
    <div className={cx(styles.list)} role="status" aria-label={t("accounts.list.loading")}>
      {[0, 1, 2].map((index) => (
        <div key={index} className={cx(styles.skeleton)} aria-hidden="true">
          <span className={cx(styles.skeletonAvatar)} />
          <span className={cx(styles.skeletonLines)}>
            <span className={cx(styles.skeletonBlock, styles.skeletonName)} />
            <span className={cx(styles.skeletonBlock, styles.skeletonMeta)} />
          </span>
        </div>
      ))}
    </div>
  );
}
