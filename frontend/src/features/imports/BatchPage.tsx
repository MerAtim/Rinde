import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router";

import { useShortDateFormatter } from "../../i18n/format";
import { withAnnouncement } from "../../shared/navigation/announcement";
import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { Checkbox } from "../../shared/ui/Checkbox";
import { cx } from "../../shared/ui/cx";
import { MoneyAmount } from "../../shared/ui/MoneyAmount";
import { Select } from "../../shared/ui/Select";
import { StatusChip } from "../../shared/ui/StatusChip";
import { useAccounts } from "../accounts/useAccounts";
import type { Category } from "../transactions/api";
import { useCategoryName } from "../transactions/presentation";
import { useCategories } from "../transactions/useTransactions";
import { type BatchLine, type ImportBatch, type ImportErrorCode, isImportsApiError } from "./api";
import styles from "./Imports.module.css";
import { useBatch, useConfirmBatch, useDiscardBatch } from "./useImports";

/** El signo se lee del string: restar en el frontend sería aritmética de dinero. */
function isExpense(line: BatchLine): boolean {
  return line.amount.amount.startsWith("-");
}

/** La vista previa de un lote: qué entra y con qué categoría (ADR-0023). */
export function BatchPage() {
  const { t } = useTranslation();
  const { batchId = "" } = useParams();
  const batch = useBatch(batchId);
  const categories = useCategories();
  // Las archivadas también: el lote pudo crearse antes de archivar la cuenta.
  const accounts = useAccounts(true);

  const notFound =
    batch.isError &&
    isImportsApiError(batch.error) &&
    batch.error.code === "IMPORT_BATCH_NOT_FOUND";

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/transactions/import" variant="text" icon="arrow-back">
          {t("imports.batch.back")}
        </LinkButton>
      </div>
      {batch.isPending || categories.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("imports.batch.loading")}
        </p>
      ) : null}
      {notFound ? <Alert>{t("imports.errors.IMPORT_BATCH_NOT_FOUND")}</Alert> : null}
      {(batch.isError && !notFound) || categories.isError ? (
        <Alert>{t("imports.errors.UNKNOWN_ERROR")}</Alert>
      ) : null}
      {batch.isSuccess && categories.isSuccess ? (
        <BatchReview
          batch={batch.data}
          categories={categories.data}
          accountName={accounts.data?.find((account) => account.id === batch.data.account_id)?.name}
        />
      ) : null}
    </div>
  );
}

interface Decision {
  included: boolean;
  categoryId: string | null;
}

interface BatchReviewProps {
  batch: ImportBatch;
  categories: Category[];
  accountName: string | undefined;
}

function BatchReview({ batch, categories, accountName }: BatchReviewProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const confirm = useConfirmBatch(batch.id);
  const discard = useDiscardBatch(batch.id);
  // Entran las nuevas; un posible duplicado, solo si la persona lo elige.
  const [decisions, setDecisions] = useState<Record<number, Decision>>(() =>
    Object.fromEntries(
      batch.lines.map((line) => [
        line.number,
        { included: line.status === "new", categoryId: line.category_id },
      ]),
    ),
  );

  const counts = {
    new: batch.lines.filter((line) => line.status === "new").length,
    duplicate: batch.lines.filter((line) => line.status === "duplicate").length,
    possible: batch.lines.filter((line) => line.status === "possible_duplicate").length,
    errors: batch.errors.length,
  };
  const chosen = batch.lines.filter((line) => decisions[line.number]?.included);
  const missingCategory = chosen.some((line) => !decisions[line.number]?.categoryId);
  const error = confirm.error ?? discard.error;
  const code: ImportErrorCode | null = error
    ? isImportsApiError(error)
      ? error.code
      : "UNKNOWN_ERROR"
    : null;

  function decide(number: number, change: Partial<Decision>) {
    setDecisions((current) => ({
      ...current,
      [number]: { included: false, categoryId: null, ...current[number], ...change },
    }));
    confirm.reset();
  }

  if (batch.confirmed) {
    return (
      <>
        <h1 className={cx(styles.title)}>{t("imports.batch.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("imports.batch.confirmed")}</p>
        <LinkButton to="/transactions" variant="tonal">
          {t("imports.batch.goToTransactions")}
        </LinkButton>
      </>
    );
  }

  return (
    <>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("imports.batch.title")}</h1>
        <p className={cx(styles.subtitle)}>
          {accountName
            ? t("imports.batch.subtitle", { file: batch.file_name, account: accountName })
            : t("imports.batch.subtitleNoAccount", { file: batch.file_name })}
        </p>
      </div>
      <ul className={cx(styles.summary)} aria-label={t("imports.batch.summaryLabel")}>
        <li>{t("imports.batch.summary.new", { count: counts.new })}</li>
        {counts.duplicate ? (
          <li>{t("imports.batch.summary.duplicate", { count: counts.duplicate })}</li>
        ) : null}
        {counts.possible ? (
          <li>{t("imports.batch.summary.possible", { count: counts.possible })}</li>
        ) : null}
        {counts.errors ? (
          <li>{t("imports.batch.summary.errors", { count: counts.errors })}</li>
        ) : null}
      </ul>
      <p className={cx(styles.muted)}>{t("imports.batch.transferHint")}</p>
      {batch.errors.length > 0 ? (
        <section className={cx(styles.problems)} aria-labelledby="import-problems">
          <h2 id="import-problems" className={cx(styles.sectionTitle)}>
            {t("imports.batch.problems.title")}
          </h2>
          <ul>
            {batch.errors.map((item) => (
              <li key={item.line}>
                {t("imports.batch.problems.line", {
                  number: item.line,
                  problem: t(`imports.batch.problems.${item.problem}`),
                })}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {code ? <Alert>{t(`imports.errors.${code}`)}</Alert> : null}
      <ul className={cx(styles.lines)}>
        {batch.lines.map((line) => (
          <LineRow
            key={line.number}
            line={line}
            categories={categories}
            decision={decisions[line.number] ?? { included: false, categoryId: null }}
            onChange={(change) => {
              decide(line.number, change);
            }}
          />
        ))}
      </ul>
      {missingCategory ? (
        <p className={cx(styles.muted)}>{t("imports.batch.missingCategory")}</p>
      ) : null}
      <div className={cx(styles.actions)}>
        <Button
          icon="check"
          isDisabled={chosen.length === 0 || missingCategory || confirm.isPending}
          onPress={() => {
            confirm.mutate(
              chosen.map((line) => ({
                number: line.number,
                category_id: decisions[line.number]?.categoryId ?? "",
              })),
              {
                onSuccess: (result) => {
                  void navigate("/transactions", {
                    state: withAnnouncement(t("imports.batch.done", { count: result.imported })),
                  });
                },
              },
            );
          }}
        >
          {t("imports.batch.confirm", { count: chosen.length })}
        </Button>
        <Button
          variant="text"
          isDisabled={discard.isPending}
          onPress={() => {
            discard.mutate(undefined, {
              onSuccess: () => {
                void navigate("/transactions/import", {
                  state: withAnnouncement(t("imports.batch.discarded", { file: batch.file_name })),
                });
              },
            });
          }}
        >
          {t("imports.batch.discard")}
        </Button>
      </div>
    </>
  );
}

interface LineRowProps {
  line: BatchLine;
  categories: Category[];
  decision: Decision;
  onChange: (change: Partial<Decision>) => void;
}

function LineRow({ line, categories, decision, onChange }: LineRowProps) {
  const { t } = useTranslation();
  const formatDate = useShortDateFormatter();
  const categoryName = useCategoryName();
  const expense = isExpense(line);
  const description = line.description ?? t("imports.batch.noDescription");
  const options = categories
    .filter((category) => category.kind === (expense ? "expense" : "income"))
    .map((category) => ({ id: category.id, label: categoryName(category) }));
  const isDuplicate = line.status === "duplicate";

  return (
    <li className={cx(styles.line)} data-included={decision.included || undefined}>
      <div className={cx(styles.lineHeader)}>
        <Checkbox
          isSelected={decision.included}
          isDisabled={isDuplicate}
          onChange={(included) => {
            onChange({ included });
          }}
        >
          <span className={cx(styles.lineText)}>
            <span className={cx(styles.lineDescription)}>{description}</span>
            <span className={cx(styles.meta)}>
              {formatDate(line.occurred_on)} ·{" "}
              {t("imports.batch.lineNumber", { number: line.number })}
            </span>
          </span>
        </Checkbox>
        {line.status === "new" ? null : (
          <StatusChip
            tone={isDuplicate ? "neutral" : "warning"}
            icon={isDuplicate ? "check-circle" : "warning"}
            label={t(`imports.batch.status.${line.status}`)}
          />
        )}
        <MoneyAmount
          amount={line.amount.amount.replace(/^-/, "")}
          currency={line.amount.currency}
          tone={expense ? "expense" : "income"}
        />
      </div>
      {decision.included ? (
        <Select
          label={t("imports.batch.categoryLabel")}
          accessibleLabel={t("imports.batch.category", { description })}
          placeholder={t("imports.batch.categoryPlaceholder")}
          options={options}
          value={decision.categoryId}
          onChange={(categoryId) => {
            onChange({ categoryId });
          }}
        />
      ) : null}
    </li>
  );
}
