import { useState } from "react";
import { Button as AriaButton, FileTrigger } from "react-aria-components";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button, LinkButton } from "../../shared/ui/Button";
import { Checkbox } from "../../shared/ui/Checkbox";
import { cx } from "../../shared/ui/cx";
import { Icon } from "../../shared/ui/Icon";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import { Select } from "../../shared/ui/Select";
import type { Account } from "../accounts/api";
import { useAccounts } from "../accounts/useAccounts";
import {
  type CsvLayout,
  type Delimiter,
  type Encoding,
  type ImportErrorCode,
  type ImportSource,
  isImportsApiError,
  MAX_FILE_BYTES,
} from "./api";
import { guessColumns } from "./columns";
import { type CsvPreview, decode, previewRows } from "./csvPreview";
import styles from "./Imports.module.css";
import { useUploadBatch } from "./useImports";

type LocalErrorCode =
  "ACCOUNT_REQUIRED" | "FILE_REQUIRED" | "COLUMNS_REQUIRED" | "COLUMNS_REPEATED";
type FormErrorCode = LocalErrorCode | ImportErrorCode;

type AmountMode = "signed" | "debit_credit";
type Kind = ImportSource["kind"];

const ACCEPTED: Record<Kind, string[]> = {
  csv: [".csv", "text/csv", "text/plain"],
  macro_pdf: [".pdf", "application/pdf"],
};

interface Columns {
  date: number | null;
  description: number | null;
  amount: number | null;
  debit: number | null;
  credit: number | null;
}

const NO_COLUMNS: Columns = {
  date: null,
  description: null,
  amount: null,
  debit: null,
  credit: null,
};

/** El archivo elegido. Un CSV se lee en el navegador para mostrar sus primeras filas; un PDF, no. */
interface Picked {
  file: File;
  bytes: ArrayBuffer | null;
}

/** El formato que arma el formulario, o el motivo por el que todavía no se puede enviar. */
function layoutFrom(
  format: Omit<CsvLayout, "date_column" | "description_column" | "amount">,
  mode: AmountMode,
  columns: Columns,
): CsvLayout | LocalErrorCode {
  const amount =
    mode === "signed"
      ? columns.amount === null
        ? null
        : ({ kind: "signed", column: columns.amount } as const)
      : columns.debit === null || columns.credit === null
        ? null
        : ({ kind: "debit_credit", debit: columns.debit, credit: columns.credit } as const);
  if (columns.date === null || columns.description === null || amount === null) {
    return "COLUMNS_REQUIRED";
  }
  const chosen = [
    columns.date,
    columns.description,
    ...(amount.kind === "signed" ? [amount.column] : [amount.debit, amount.credit]),
  ];
  if (new Set(chosen).size !== chosen.length) {
    return "COLUMNS_REPEATED";
  }
  return {
    ...format,
    date_column: columns.date,
    description_column: columns.description,
    amount,
  };
}

/** Subir un CSV con su formato, o el resumen PDF de Macro (ADR-0023). La vista previa viene después. */
export function ImportPage() {
  const { t } = useTranslation();
  const accounts = useAccounts(false);

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.back)}>
        <LinkButton to="/transactions" variant="text" icon="arrow-back">
          {t("imports.back")}
        </LinkButton>
      </div>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("imports.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("imports.subtitle")}</p>
      </div>
      {accounts.isPending ? (
        <p role="status" className={cx(styles.muted)}>
          {t("imports.loading")}
        </p>
      ) : null}
      {accounts.isError ? <Alert>{t("imports.errors.UNKNOWN_ERROR")}</Alert> : null}
      {accounts.isSuccess ? <ImportForm accounts={accounts.data} /> : null}
    </div>
  );
}

function ImportForm({ accounts }: { accounts: Account[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const upload = useUploadBatch();
  const [accountId, setAccountId] = useState(accounts.length === 1 ? (accounts[0]?.id ?? "") : "");
  const [kind, setKind] = useState<Kind>("csv");
  const [picked, setPicked] = useState<Picked | null>(null);
  const [encoding, setEncoding] = useState<Encoding>("utf-8");
  const [delimiter, setDelimiter] = useState<Delimiter>(";");
  const [decimalMark, setDecimalMark] = useState<CsvLayout["decimal_mark"]>("comma");
  const [dateOrder, setDateOrder] = useState<CsvLayout["date_order"]>("dmy");
  const [hasHeader, setHasHeader] = useState(true);
  const [mode, setMode] = useState<AmountMode>("signed");
  const [columns, setColumns] = useState<Columns>(NO_COLUMNS);
  const [localError, setLocalError] = useState<FormErrorCode | null>(null);

  const isCsv = kind === "csv";
  const text = picked?.bytes ? decode(picked.bytes, encoding) : null;
  const preview: CsvPreview | null = text === null ? null : previewRows(text, delimiter);
  const header = hasHeader && preview ? (preview.rows[0] ?? []) : [];
  const columnOptions = Array.from({ length: preview?.columns ?? 0 }, (_, index) => {
    const name = header[index]?.trim();
    return {
      id: String(index),
      label: name
        ? t("imports.columns.optionNamed", { number: index + 1, name })
        : t("imports.columns.option", { number: index + 1 }),
    };
  });

  const serverError: FormErrorCode | null = upload.error
    ? isImportsApiError(upload.error)
      ? upload.error.code
      : "UNKNOWN_ERROR"
    : null;
  const code = localError ?? serverError;

  function submit(file: File, source: ImportSource) {
    upload.mutate(
      { accountId, file, source },
      {
        onSuccess: (batch) => {
          void navigate(`/imports/${batch.id}`);
        },
      },
    );
  }

  function reset() {
    setLocalError(null);
    upload.reset();
  }

  /** Con un archivo o un formato nuevo, se vuelven a proponer columnas desde los títulos. */
  function propose(next: { bytes: ArrayBuffer; encoding: Encoding; delimiter: Delimiter }) {
    const decoded = decode(next.bytes, next.encoding);
    const first = decoded === null ? [] : (previewRows(decoded, next.delimiter, 1).rows[0] ?? []);
    const guess = guessColumns(first);
    setColumns(guess);
    setMode(guess.amount === null && guess.debit !== null ? "debit_credit" : "signed");
  }

  function choose(key: keyof Columns, value: string) {
    setColumns((current) => ({ ...current, [key]: Number(value) }));
    reset();
  }

  function columnSelect(key: keyof Columns, label: string) {
    const value = columns[key];
    return (
      <Select
        label={label}
        placeholder={t("imports.columns.placeholder")}
        options={columnOptions}
        value={value === null ? null : String(value)}
        onChange={(next) => {
          choose(key, next);
        }}
      />
    );
  }

  return (
    <form
      className={cx(styles.form)}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (!isCsv) {
          const missing = !accountId ? "ACCOUNT_REQUIRED" : !picked ? "FILE_REQUIRED" : null;
          setLocalError(missing);
          if (picked && !missing) {
            submit(picked.file, { kind });
          }
          return;
        }
        const layout = layoutFrom(
          {
            delimiter,
            encoding,
            decimal_mark: decimalMark,
            date_order: dateOrder,
            has_header: hasHeader,
          },
          mode,
          columns,
        );
        const invalid: LocalErrorCode | null = !accountId
          ? "ACCOUNT_REQUIRED"
          : !picked
            ? "FILE_REQUIRED"
            : typeof layout === "string"
              ? layout
              : null;
        setLocalError(invalid);
        if (invalid || !picked || typeof layout === "string") {
          return;
        }
        submit(picked.file, { kind: "csv", layout });
      }}
    >
      {code ? <Alert>{t(`imports.errors.${code}`)}</Alert> : null}
      <Select
        label={t("imports.account")}
        placeholder={t("imports.accountPlaceholder")}
        options={accounts.map((account) => ({
          id: account.id,
          label: `${account.name} (${account.currency})`,
        }))}
        value={accountId || null}
        onChange={(value) => {
          setAccountId(value);
          reset();
        }}
      />
      <SegmentedButton
        label={t("imports.kind.label")}
        isLabelVisible
        options={[
          { id: "csv", label: t("imports.kind.csv") },
          { id: "macro_pdf", label: t("imports.kind.macroPdf") },
        ]}
        value={kind}
        onChange={(value) => {
          setKind(value);
          // Un CSV elegido no sirve como PDF, ni al revés.
          setPicked(null);
          reset();
        }}
      />
      <div className={cx(styles.file)}>
        <p className={cx(styles.label)} id="import-file-label">
          {t("imports.file.label")}
        </p>
        <FileTrigger
          acceptedFileTypes={ACCEPTED[kind]}
          onSelect={(list) => {
            const file = list?.[0];
            if (!file) {
              return;
            }
            reset();
            if (file.size > MAX_FILE_BYTES) {
              setPicked(null);
              setLocalError("IMPORT_FILE_TOO_LARGE");
              return;
            }
            if (!isCsv) {
              setPicked({ file, bytes: null });
              return;
            }
            void file.arrayBuffer().then((bytes) => {
              setPicked({ file, bytes });
              propose({ bytes, encoding, delimiter });
            });
          }}
        >
          <AriaButton
            className={cx("state-layer", styles.fileButton)}
            aria-describedby="import-file-label import-file-hint"
          >
            <Icon name="upload" size={20} />
            {picked
              ? t("imports.file.change")
              : isCsv
                ? t("imports.file.choose")
                : t("imports.file.choosePdf")}
          </AriaButton>
        </FileTrigger>
        {picked ? <p className={cx(styles.fileName)}>{picked.file.name}</p> : null}
        <p className={cx(styles.muted)} id="import-file-hint">
          {isCsv ? t("imports.file.hint") : t("imports.file.hintPdf")}
        </p>
      </div>

      {isCsv ? (
        <CsvFormat
          encoding={encoding}
          delimiter={delimiter}
          decimalMark={decimalMark}
          dateOrder={dateOrder}
          hasHeader={hasHeader}
          onEncoding={(value) => {
            setEncoding(value);
            reset();
            if (picked?.bytes) {
              propose({ bytes: picked.bytes, encoding: value, delimiter });
            }
          }}
          onDelimiter={(value) => {
            setDelimiter(value);
            reset();
            if (picked?.bytes) {
              propose({ bytes: picked.bytes, encoding, delimiter: value });
            }
          }}
          onDecimalMark={(value) => {
            setDecimalMark(value);
            reset();
          }}
          onDateOrder={(value) => {
            setDateOrder(value);
            reset();
          }}
          onHeader={(value) => {
            setHasHeader(value);
            reset();
          }}
        />
      ) : null}

      {isCsv && picked && text === null ? (
        <Alert>
          {t("imports.sample.unreadable", {
            encoding:
              encoding === "utf-8" ? t("imports.format.utf8") : t("imports.format.windows1252"),
          })}
        </Alert>
      ) : null}
      {isCsv && preview && preview.rows.length > 0 ? (
        <Sample preview={preview} hasHeader={hasHeader} />
      ) : null}

      {isCsv && preview && preview.columns > 0 ? (
        <fieldset className={cx(styles.fieldset)}>
          <legend className={cx(styles.legend)}>{t("imports.columns.title")}</legend>
          {columnSelect("date", t("imports.columns.date"))}
          {columnSelect("description", t("imports.columns.description"))}
          <SegmentedButton
            label={t("imports.columns.amountMode")}
            isLabelVisible
            options={[
              { id: "signed", label: t("imports.columns.signed") },
              { id: "debit_credit", label: t("imports.columns.debitCredit") },
            ]}
            value={mode}
            onChange={(value) => {
              setMode(value);
              reset();
            }}
          />
          {mode === "signed" ? (
            columnSelect("amount", t("imports.columns.amount"))
          ) : (
            <>
              {columnSelect("debit", t("imports.columns.debit"))}
              {columnSelect("credit", t("imports.columns.credit"))}
            </>
          )}
        </fieldset>
      ) : null}

      <div className={cx(styles.actions)}>
        <Button type="submit" icon="check" isDisabled={upload.isPending}>
          {t("imports.submit")}
        </Button>
      </div>
    </form>
  );
}

function Sample({ preview, hasHeader }: { preview: CsvPreview; hasHeader: boolean }) {
  const { t } = useTranslation();
  const [first, ...rest] = preview.rows;
  const body = hasHeader ? rest : preview.rows;
  const titles = Array.from({ length: preview.columns }, (_, index) =>
    hasHeader && first?.[index]?.trim()
      ? first[index]
      : t("imports.columns.option", { number: index + 1 }),
  );

  return (
    <div
      className={cx(styles.sample)}
      role="region"
      aria-label={t("imports.sample.title")}
      tabIndex={0}
    >
      <table className={cx(styles.table)}>
        <caption className={cx(styles.caption)}>{t("imports.sample.caption")}</caption>
        <thead>
          <tr>
            {titles.map((title, index) => (
              <th key={index} scope="col">
                {title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {titles.map((_, index) => (
                <td key={index}>{row[index] ?? ""}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface CsvFormatProps {
  encoding: Encoding;
  delimiter: Delimiter;
  decimalMark: CsvLayout["decimal_mark"];
  dateOrder: CsvLayout["date_order"];
  hasHeader: boolean;
  onEncoding: (value: Encoding) => void;
  onDelimiter: (value: Delimiter) => void;
  onDecimalMark: (value: CsvLayout["decimal_mark"]) => void;
  onDateOrder: (value: CsvLayout["date_order"]) => void;
  onHeader: (value: boolean) => void;
}

/** Cómo está escrito el CSV. El PDF de Macro no lo necesita: su formato es fijo. */
function CsvFormat({
  encoding,
  delimiter,
  decimalMark,
  dateOrder,
  hasHeader,
  onEncoding,
  onDelimiter,
  onDecimalMark,
  onDateOrder,
  onHeader,
}: CsvFormatProps) {
  const { t } = useTranslation();
  return (
    <fieldset className={cx(styles.fieldset)}>
      <legend className={cx(styles.legend)}>{t("imports.format.title")}</legend>
      <SegmentedButton
        label={t("imports.format.encoding")}
        isLabelVisible
        options={[
          { id: "utf-8", label: t("imports.format.utf8") },
          { id: "windows-1252", label: t("imports.format.windows1252") },
        ]}
        value={encoding}
        onChange={onEncoding}
      />
      <SegmentedButton
        label={t("imports.format.delimiter")}
        isLabelVisible
        options={[
          { id: ";", label: t("imports.format.semicolon") },
          { id: ",", label: t("imports.format.comma") },
          { id: "\t", label: t("imports.format.tab") },
        ]}
        value={delimiter}
        onChange={onDelimiter}
      />
      <SegmentedButton
        label={t("imports.format.decimal")}
        isLabelVisible
        options={[
          { id: "comma", label: t("imports.format.decimalComma") },
          { id: "dot", label: t("imports.format.decimalDot") },
        ]}
        value={decimalMark}
        onChange={onDecimalMark}
      />
      <SegmentedButton
        label={t("imports.format.date")}
        isLabelVisible
        options={[
          { id: "dmy", label: t("imports.format.dateDmy") },
          { id: "iso", label: t("imports.format.dateIso") },
        ]}
        value={dateOrder}
        onChange={onDateOrder}
      />
      <Checkbox isSelected={hasHeader} onChange={onHeader}>
        {t("imports.format.header")}
      </Checkbox>
    </fieldset>
  );
}
