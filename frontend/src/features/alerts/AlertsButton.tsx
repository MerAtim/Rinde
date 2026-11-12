import { useTranslation } from "react-i18next";

import { useLocale } from "../../i18n/format";
import { LinkIconButton } from "../../shared/ui/IconButton";
import { useAlerts } from "./useAlerts";

/**
 * Más que esto se resume como "9+": con dos cifras el badge tapa la campana.
 * El número exacto está en el nombre accesible y en la pantalla de alertas.
 */
const BADGE_MAX = 9;

/** La campana de la barra superior: lleva a las alertas y dice cuántas hay sin leer. */
export function AlertsButton() {
  const { t } = useTranslation();
  const locale = useLocale();
  const alerts = useAlerts();
  const unread = alerts.data?.unread ?? 0;
  const count = new Intl.NumberFormat(locale);

  return (
    <LinkIconButton
      to="/alerts"
      icon={unread > 0 ? "notifications-fill" : "notifications"}
      // El badge es solo visual: el número también está en el nombre accesible.
      label={unread > 0 ? t("alerts.openUnread", { count: unread }) : t("alerts.open")}
      badge={
        unread === 0
          ? ""
          : unread > BADGE_MAX
            ? t("alerts.badgeOverflow", { max: count.format(BADGE_MAX) })
            : count.format(unread)
      }
    />
  );
}
