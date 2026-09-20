import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { useDateFormatter } from "../../i18n/format";
import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { ConfirmDialog } from "../../shared/ui/ConfirmDialog";
import { cx } from "../../shared/ui/cx";
import { Icon } from "../../shared/ui/Icon";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import { StatusChip } from "../../shared/ui/StatusChip";
import { TextField } from "../../shared/ui/TextField";
import styles from "./Accounts.module.css";
import { type Account, type AccountErrorCode, isAccountsApiError } from "./api";
import { errorCodeOf, fieldOf, validateName } from "./errors";
import { HistoryWithUndo } from "../transactions/HistoryList";
import {
  balancesById,
  flattenHistory,
  useBalances,
  useCategories,
  useHistory,
} from "../transactions/useTransactions";
import { KIND_ICON } from "./presentation";
import { useAccount, useAccounts, useArchiveAccount, useRenameAccount } from "./useAccounts";

/**
 * Una cuenta ajena responde igual que una inexistente (ADR-0009), y un
 * identificador mal formado lo rechaza la validación (422): para la persona,
 * los tres casos son "no encontramos esta cuenta".
 */
function isNotFound(error: unknown): boolean {
  return isAccountsApiError(error) && (error.status === 404 || error.status === 422);
}

export function AccountPage() {
  const { t } = useTranslation();
  const { accountId = "" } = useParams();
  const account = useAccount(accountId);

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/accounts" variant="text" icon="arrow-back">
          {t("accounts.detail.back")}
        </LinkButton>
      </div>
      {account.isPending ? (
        <p role="status" className={cx(styles.subtitle)}>
          {t("accounts.detail.loading")}
        </p>
      ) : null}
      {account.isError && isNotFound(account.error) ? (
        <section className={cx(styles.empty)} aria-labelledby="account-not-found">
          <h1 id="account-not-found" className={cx(styles.emptyTitle)}>
            {t("accounts.detail.notFoundTitle")}
          </h1>
          <p className={cx(styles.emptyBody)}>{t("accounts.detail.notFoundBody")}</p>
        </section>
      ) : null}
      {account.isError && !isNotFound(account.error) ? (
        <div className={cx(styles.problem)}>
          <Alert>{t("accounts.detail.error")}</Alert>
          <Button
            variant="tonal"
            onPress={() => {
              void account.refetch();
            }}
          >
            {t("accounts.list.retry")}
          </Button>
        </div>
      ) : null}
      {account.isSuccess ? <AccountDetail account={account.data} /> : null}
    </div>
  );
}

function AccountDetail({ account }: { account: Account }) {
  const { t } = useTranslation();
  const formatDate = useDateFormatter();

  return (
    <>
      <header className={cx(styles.identity)}>
        <span className={cx(styles.avatar, styles.avatarLarge)}>
          <Icon name={KIND_ICON[account.kind]} size={28} />
        </span>
        <div className={cx(styles.heading)}>
          <h1 className={cx(styles.title)}>{account.name}</h1>
          <p className={cx(styles.meta)}>
            {t(`accounts.kind.${account.kind}`)} · {t(`accounts.currency.${account.currency}`)}
          </p>
          <p className={cx(styles.meta)}>
            {t("accounts.detail.openedOn", { date: formatDate(account.created_at) })}
          </p>
        </div>
      </header>
      <AccountMoney account={account} />
      {account.archived_at ? (
        <section className={cx(styles.section)}>
          <div>
            <StatusChip
              tone="neutral"
              icon="archive"
              label={t("accounts.detail.archivedOn", { date: formatDate(account.archived_at) })}
            />
          </div>
          <p className={cx(styles.sectionBody)}>{t("accounts.detail.archivedExplain")}</p>
        </section>
      ) : (
        <>
          {/* La clave reinicia el borrador si cambia de cuenta sin desmontar la pantalla. */}
          <RenameSection key={account.id} account={account} />
          <ArchiveSection account={account} />
        </>
      )}
    </>
  );
}

/**
 * Saldo de la cuenta y sus últimos movimientos, transferencias incluidas.
 *
 * Es una sola lista y no dos secciones: para quien mira su cuenta, una
 * transferencia que le sacó plata es un movimiento más. Lo que la distingue es
 * que del otro lado entró, y eso se ve en la otra cuenta (ADR-0014).
 */
function AccountMoney({ account }: { account: Account }) {
  const { t } = useTranslation();
  const balance = balancesById(useBalances().data).get(account.id);
  const history = useHistory({ accountId: account.id, limit: 5 });
  const categories = useCategories();
  // Las archivadas también: una transferencia vieja puede apuntar a una de ellas.
  const accounts = useAccounts(true);
  const rows = flattenHistory(history.data);

  return (
    <section className={cx(styles.section)} aria-labelledby="account-money">
      <h2 id="account-money" className={cx(styles.sectionTitle)}>
        {t("accounts.detail.balance")}
      </h2>
      {/* Sin movimientos, el saldo es cero en la moneda de la cuenta. */}
      <MoneyAmount amount={balance?.amount ?? "0"} currency={account.currency} size="hero" />
      <HistoryWithUndo
        entries={rows}
        categories={categories.data ?? []}
        accounts={accounts.data ?? [account]}
        showAccount={false}
        perspective={account.id}
      />
      {history.isSuccess && rows.length === 0 ? (
        <p className={cx(styles.sectionBody)}>{t("accounts.detail.noMovements")}</p>
      ) : null}
      <div className={cx(styles.actions)}>
        {account.archived_at ? null : (
          <LinkButton to={`/transactions/new?account=${account.id}`} icon="add">
            {t("transactions.list.add")}
          </LinkButton>
        )}
        {account.archived_at ? null : (
          <LinkButton to={`/transfers/new?account=${account.id}`} variant="tonal" icon="swap">
            {t("transfers.detail.add")}
          </LinkButton>
        )}
        {rows.length > 0 ? (
          <LinkButton to={`/transactions?account=${account.id}`} variant="text">
            {t("accounts.detail.allMovements")}
          </LinkButton>
        ) : null}
      </div>
    </section>
  );
}

function RenameSection({ account }: { account: Account }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(account.name);
  const [localError, setLocalError] = useState<AccountErrorCode | null>(null);
  const rename = useRenameAccount(account.id);

  const code = localError ?? errorCodeOf(rename.error);
  const field = code ? fieldOf(code) : null;
  const message = code ? t(`accounts.errors.${code}`) : "";

  return (
    <section className={cx(styles.section)} aria-labelledby="rename-title">
      <h2 id="rename-title" className={cx(styles.sectionTitle)}>
        {t("accounts.detail.renameTitle")}
      </h2>
      {field === "form" ? <Alert>{message}</Alert> : null}
      <form
        className={cx(styles.form)}
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          const error = validateName(draft);
          setLocalError(error);
          if (!error) {
            rename.mutate(draft);
          }
        }}
      >
        <TextField
          label={t("accounts.fields.name")}
          value={draft}
          onChange={(value) => {
            setDraft(value);
            setLocalError(null);
            rename.reset();
          }}
          autoComplete="off"
          isRequired
          validationBehavior="aria"
          {...(field === "name" ? { errorMessage: message } : {})}
        />
        <div className={cx(styles.actions)}>
          <Button type="submit" isDisabled={rename.isPending}>
            {rename.isPending ? t("accounts.detail.renaming") : t("accounts.detail.rename")}
          </Button>
          <p role="status" className={cx(styles.sectionBody)}>
            {rename.isSuccess ? t("accounts.detail.renamed") : ""}
          </p>
        </div>
      </form>
    </section>
  );
}

function ArchiveSection({ account }: { account: Account }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isConfirming, setConfirming] = useState(false);
  const archive = useArchiveAccount(account.id);
  const code = errorCodeOf(archive.error);

  return (
    <section className={cx(styles.section)} aria-labelledby="archive-title">
      <h2 id="archive-title" className={cx(styles.sectionTitle)}>
        {t("accounts.detail.archiveTitle")}
      </h2>
      <p className={cx(styles.sectionBody)}>{t("accounts.detail.archiveExplain")}</p>
      <div className={cx(styles.actions)}>
        <Button
          variant="outlined"
          icon="archive"
          onPress={() => {
            archive.reset();
            setConfirming(true);
          }}
        >
          {t("accounts.detail.archive")}
        </Button>
      </div>
      {/* Sin "Deshacer": la API no tiene desarchivar, así que es irreversible y se confirma. */}
      <ConfirmDialog
        isOpen={isConfirming}
        onOpenChange={setConfirming}
        title={t("accounts.detail.confirmTitle", { name: account.name })}
        confirmLabel={
          archive.isPending ? t("accounts.detail.confirming") : t("accounts.detail.confirm")
        }
        cancelLabel={t("accounts.detail.cancel")}
        isPending={archive.isPending}
        onConfirm={() => {
          archive.mutate(undefined, {
            onSuccess: (archived) => {
              setConfirming(false);
              void navigate("/accounts", {
                state: withAnnouncement(t("accounts.list.archivedNotice", { name: archived.name })),
              });
            },
          });
        }}
      >
        <p>{t("accounts.detail.confirmBody")}</p>
        {code ? <Alert>{t(`accounts.errors.${code}`)}</Alert> : null}
      </ConfirmDialog>
    </section>
  );
}
