import { useTranslation } from "react-i18next";

import { useMoneyFormatter } from "../../i18n/format";
import { cx } from "../../shared/ui/cx";
import type { Preferences } from "../preferences/api";
import { useConversion } from "../rates/useRates";
import styles from "./Accounts.module.css";
import type { Currency } from "./api";

interface EquivalentProps {
  amount: string;
  currency: Currency;
  preferences: Preferences;
}

/**
 * El saldo en la moneda de referencia, con el dólar elegido y la cotización de
 * hoy (ADR-0017). Lo calcula el servidor: acá no se multiplica plata.
 *
 * No aparece si la cuenta ya está en esa moneda. Bitcoin pasa primero a
 * dólares con su precio y, si hace falta, a pesos con el dólar elegido
 * (ADR-0029): el texto dice los dos. Si no hay cotización, lo dice: nunca
 * muestra un número adivinado.
 */
export function Equivalent({ amount, currency, preferences }: EquivalentProps) {
  const { t } = useTranslation();
  const money = useMoneyFormatter();
  const target = preferences.reference_currency;
  const applies = currency !== target;
  const conversion = useConversion(
    applies ? { rateType: preferences.rate_type, amount, currency, target } : null,
  );

  if (!applies || conversion.isPending) {
    return null;
  }
  if (conversion.isError) {
    return <span className={cx(styles.equivalent)}>{t("accounts.equivalent.unavailable")}</span>;
  }
  const converted = money(conversion.data.converted.amount, conversion.data.converted.currency);
  const rate = t(`rates.at.${preferences.rate_type}`);
  let text = t("accounts.equivalent.value", { amount: converted, rate });
  if (currency === "BTC") {
    text =
      target === "USD"
        ? t("accounts.equivalent.bitcoin", { amount: converted })
        : t("accounts.equivalent.bitcoinAndRate", { amount: converted, rate });
  }
  return <span className={cx(styles.equivalent)}>{text}</span>;
}
