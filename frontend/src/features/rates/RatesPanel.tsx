import { useTranslation } from "react-i18next";

import { useRateFormatter, useShortDateFormatter } from "../../i18n/format";
import { cx } from "../../shared/ui/cx";
import { isRatesApiError, type Quote } from "./api";
import styles from "./RatesPanel.module.css";
import { useTodayRates } from "./useRates";

/**
 * El dólar de hoy, en sus distintas versiones (ADR-0016).
 *
 * Una tabla de verdad y no tarjetas sueltas: se lee por filas con un lector de
 * pantalla, y las cifras quedan alineadas en columnas para comparar.
 */
export function RatesPanel() {
  const { t } = useTranslation();
  const rates = useTodayRates();

  return (
    <section aria-labelledby="rates-heading" className={cx(styles.card)}>
      <h2 id="rates-heading" className={cx("type-label-medium", styles.heading)}>
        {t("rates.heading")}
      </h2>
      {rates.status === "pending" && (
        <p role="status" className={cx("type-body-large", styles.message)}>
          {t("rates.loading")}
        </p>
      )}
      {rates.status === "error" && (
        <p role="alert" className={cx("type-body-large", styles.message)}>
          {isRatesApiError(rates.error) && rates.error.code === "RATES_UNAVAILABLE"
            ? t("rates.unavailable")
            : t("rates.error")}
        </p>
      )}
      {rates.status === "success" &&
        (rates.data.length === 0 ? (
          <p role="status" className={cx("type-body-large", styles.message)}>
            {t("rates.empty")}
          </p>
        ) : (
          <RatesTable quotes={rates.data} />
        ))}
    </section>
  );
}

function RatesTable({ quotes }: { quotes: Quote[] }) {
  const { t } = useTranslation();

  return (
    <table className={cx(styles.table)}>
      <caption className={cx(styles.caption)}>{t("rates.caption")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("rates.columns.type")}</th>
          <th scope="col" className={cx(styles.number)}>
            {t("rates.columns.buy")}
          </th>
          <th scope="col" className={cx(styles.number)}>
            {t("rates.columns.sell")}
          </th>
        </tr>
      </thead>
      <tbody>
        {quotes.map((quote) => (
          <RateRow key={quote.rate_type} quote={quote} />
        ))}
      </tbody>
    </table>
  );
}

function RateRow({ quote }: { quote: Quote }) {
  const { t } = useTranslation();
  const rate = useRateFormatter();
  const date = useShortDateFormatter();
  const source = t(`rates.sources.${quote.source}`);
  // Un feriado, el oficial de hoy es el del último día hábil: se dice, no se esconde.
  const updatedOn = quote.updated_at ? argentineDay(quote.updated_at) : null;
  const detail =
    updatedOn !== null && updatedOn !== quote.day
      ? t("rates.updatedOn", { date: date(updatedOn), source })
      : source;

  return (
    <tr>
      <th scope="row" className={cx(styles.type)}>
        <span>{t(`rates.types.${quote.rate_type}`)}</span>
        <span className={cx(styles.detail)}>{detail}</span>
      </th>
      <td className={cx("numeric", styles.number)}>{rate(quote.buy)}</td>
      <td className={cx("numeric", styles.number)}>{rate(quote.sell)}</td>
    </tr>
  );
}

const ARGENTINE_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Argentina/Buenos_Aires",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/**
 * El día de Argentina en que cae un momento, como AAAA-MM-DD (`en-CA` formatea
 * así). Es el mismo criterio que usa el servidor para decir qué día es "hoy".
 */
function argentineDay(moment: string): string {
  return ARGENTINE_DAY.format(new Date(moment));
}
