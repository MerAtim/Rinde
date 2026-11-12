import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router";

import { Snackbar } from "../../shared/ui/Snackbar";
import { useCategoryName } from "../transactions/presentation";
import type { AlertFeed, BudgetAlert } from "./api";
import { useAlerts } from "./useAlerts";

interface Seen {
  feed: AlertFeed | undefined;
  /** `null` hasta la primera lista: lo que ya estaba al entrar no se avisa. */
  ids: ReadonlySet<string> | null;
}

/**
 * El aviso breve cuando llega una alerta nueva, por ejemplo al guardar el gasto
 * que la disparó (ADR-0022). En la pantalla de alertas no hace falta: ya se ve.
 */
export function AlertNotice() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const categoryName = useCategoryName();
  const { data } = useAlerts();
  const [seen, setSeen] = useState<Seen>({ feed: undefined, ids: null });
  const [fresh, setFresh] = useState<BudgetAlert | null>(null);

  // Se compara al cambiar la lista, durante el render y no en un efecto: es
  // estado que se deriva de los datos (react.dev, "You might not need an effect").
  if (data !== seen.feed) {
    const known = seen.ids;
    if (data && known) {
      const newcomer = data.alerts.find((alert) => !alert.read && !known.has(alert.id));
      if (newcomer) {
        setFresh(newcomer);
      }
    }
    setSeen({
      feed: data,
      ids: data ? new Set([...(known ?? []), ...data.alerts.map((alert) => alert.id)]) : known,
    });
  }

  if (!fresh || location.pathname === "/alerts") {
    return null;
  }

  return (
    <Snackbar
      message={t(`alerts.message.${fresh.threshold}`, { name: categoryName(fresh.category) })}
      onDismiss={() => {
        setFresh(null);
      }}
      action={{
        label: t("alerts.noticeAction"),
        icon: "notifications",
        onPress: () => {
          setFresh(null);
          void navigate("/alerts");
        },
      }}
    />
  );
}
