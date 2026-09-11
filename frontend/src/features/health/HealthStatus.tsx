import { useTranslation } from "react-i18next";

import { cx } from "../../shared/ui/cx";
import type { IconName } from "../../shared/ui/Icon";
import { StatusChip, type StatusTone } from "../../shared/ui/StatusChip";
import styles from "./HealthStatus.module.css";
import { useReadiness } from "./useReadiness";

type HealthState = "checking" | "ok" | "unavailable" | "error";

const PRESENTATION: Record<HealthState, { tone: StatusTone; icon: IconName }> = {
  checking: { tone: "neutral", icon: "schedule" },
  ok: { tone: "ok", icon: "check-circle" },
  unavailable: { tone: "warning", icon: "warning" },
  error: { tone: "error", icon: "error" },
};

function stateOf(query: ReturnType<typeof useReadiness>): HealthState {
  switch (query.status) {
    case "pending":
      return "checking";
    case "error":
      return "error";
    case "success":
      return query.data.status === "ok" ? "ok" : "unavailable";
  }
}

export function HealthStatus() {
  const { t } = useTranslation();
  const state = stateOf(useReadiness());
  const { tone, icon } = PRESENTATION[state];

  return (
    <section aria-labelledby="health-heading" className={cx(styles.card)}>
      <div className={cx(styles.head)}>
        <h2 id="health-heading" className={cx("type-label-medium", styles.heading)}>
          {t("health.heading")}
        </h2>
        <StatusChip tone={tone} icon={icon} label={t(`health.status.${state}`)} />
      </div>
      <p role="status" className={cx("type-body-large", styles.message)}>
        {t(`health.${state}`)}
      </p>
    </section>
  );
}
