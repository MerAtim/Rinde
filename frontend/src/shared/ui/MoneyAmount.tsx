import { useTranslation } from "react-i18next";

import { useMoneyFormatter } from "../../i18n/format";
import { cx } from "./cx";
import { Icon } from "./Icon";
import styles from "./MoneyAmount.module.css";

export type MoneyTone = "income" | "expense" | "neutral";

interface MoneyAmountProps {
  /** String decimal tal como lo devuelve la API: acá no se hace aritmética. */
  amount: string;
  currency: string;
  tone?: MoneyTone;
  /** Tamaño grande para el saldo de una cuenta. */
  size?: "row" | "hero";
}

/**
 * Un monto con su signo y su flecha, además del color: quien no distingue
 * rojo de verde tiene que entender igual si entró o salió plata (WCAG 1.4.1).
 */
export function MoneyAmount({
  amount,
  currency,
  tone = "neutral",
  size = "row",
}: MoneyAmountProps) {
  const { t } = useTranslation();
  const format = useMoneyFormatter();
  const sign = tone === "income" ? "+" : tone === "expense" ? "−" : "";

  return (
    <span className={cx("numeric", styles.amount, styles[size])} data-tone={tone}>
      {tone === "neutral" ? null : (
        <>
          {/* La palabra la lee el lector de pantalla; el signo y la flecha se ven. */}
          <span className="visually-hidden">{t(`money.${tone}`)}</span>
          <Icon name={tone === "income" ? "movement-in" : "movement-out"} size={16} />
        </>
      )}
      <span>
        {sign}
        {format(amount, currency)}
      </span>
    </span>
  );
}
