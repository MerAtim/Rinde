import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { SegmentedButton } from "../../shared/ui/SegmentedButton";
import { Select } from "../../shared/ui/Select";
import styles from "./PreferencesPage.module.css";
import { isPreferencesApiError, type Preferences, RATE_TYPES, REFERENCE_CURRENCIES } from "./api";
import { usePreferences, useUpdatePreferences } from "./usePreferences";

/** Con qué moneda y qué dólar se muestran los equivalentes (ADR-0017). */
export function PreferencesPage() {
  const { t } = useTranslation();
  const preferences = usePreferences();

  return (
    <div className={cx(styles.page)}>
      <div className={cx(styles.heading)}>
        <h1 className={cx(styles.title)}>{t("preferences.title")}</h1>
        <p className={cx(styles.subtitle)}>{t("preferences.subtitle")}</p>
      </div>
      {preferences.isPending ? (
        <p role="status" className={cx(styles.message)}>
          {t("preferences.loading")}
        </p>
      ) : null}
      {preferences.isError ? <Alert>{t("preferences.loadError")}</Alert> : null}
      {/* El formulario arranca con lo guardado: se monta recién cuando llegó. */}
      {preferences.isSuccess ? <PreferencesForm saved={preferences.data} /> : null}
    </div>
  );
}

function PreferencesForm({ saved }: { saved: Preferences }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<Preferences>(saved);
  const update = useUpdatePreferences();

  function change(next: Partial<Preferences>) {
    setDraft((current) => ({ ...current, ...next }));
    update.reset();
  }

  const errorCode = update.error
    ? isPreferencesApiError(update.error)
      ? update.error.code
      : "UNKNOWN_ERROR"
    : null;

  return (
    <form
      className={cx(styles.form)}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate(draft);
      }}
    >
      {errorCode ? <Alert>{t(`preferences.errors.${errorCode}`)}</Alert> : null}
      <SegmentedButton
        label={t("preferences.fields.currency")}
        isLabelVisible
        description={t("preferences.fields.currencyHelp")}
        options={REFERENCE_CURRENCIES.map((id) => ({
          id,
          label: id,
          accessibleLabel: t(`accounts.currency.${id}`),
        }))}
        value={draft.reference_currency}
        onChange={(reference_currency) => {
          change({ reference_currency });
        }}
      />
      <Select
        label={t("preferences.fields.rateType")}
        placeholder={t("preferences.fields.rateType")}
        options={RATE_TYPES.map((id) => ({ id, label: t(`rates.types.${id}`) }))}
        value={draft.rate_type}
        onChange={(value) => {
          const rate_type = RATE_TYPES.find((id) => id === value);
          if (rate_type) {
            change({ rate_type });
          }
        }}
        description={t(`preferences.rateTypeHelp.${draft.rate_type}`)}
      />
      <div className={cx(styles.actions)}>
        <Button type="submit" isDisabled={update.isPending}>
          {update.isPending ? t("preferences.saving") : t("preferences.save")}
        </Button>
        <p role="status" className={cx(styles.message)}>
          {update.isSuccess ? t("preferences.saved") : ""}
        </p>
      </div>
    </form>
  );
}
