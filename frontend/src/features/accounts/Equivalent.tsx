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
 * No aparece si la cuenta ya está en esa moneda, ni para Bitcoin, que todavía
 * no tiene cotización. Si no hay cotización, lo dice: nunca muestra un número
 * adivinado.
 */
export function Equivalent({ amount, currency, preferences }: EquivalentProps) {
  const { t } = useTranslation();
  const money = useMoneyFormatter();
  const target = preferences.reference_currency;
  const applies = currency !== target && currency !== "BTC";
  const conversion = useConversion(
    applies ? { rateType: preferences.rate_type, amount, currency, target } : null,
  );

  if (!applies || conversion.isPending) {
    return null;
  }
  const rate = t(`rates.at.${preferences.rate_type}`);
  return (
    <span className={cx(styles.equivalent)}>
      {conversion.isError
        ? t("accounts.equivalent.unavailable")
        : t("accounts.equivalent.value", {
            amount: money(conversion.data.converted.amount, conversion.data.converted.currency),
            rate,
          })}
    </span>
  );
}
