import { useTranslation } from "react-i18next";

import { useReadiness } from "./useReadiness";

type Tone = "neutral" | "ok" | "warning" | "error";
type MessageKey = "health.checking" | "health.ok" | "health.unavailable" | "health.error";

function describe(query: ReturnType<typeof useReadiness>): { key: MessageKey; tone: Tone } {
  switch (query.status) {
    case "pending":
      return { key: "health.checking", tone: "neutral" };
    case "error":
      return { key: "health.error", tone: "error" };
    case "success":
      return query.data.status === "ok"
        ? { key: "health.ok", tone: "ok" }
        : { key: "health.unavailable", tone: "warning" };
  }
}

export function HealthStatus() {
  const { t } = useTranslation();
  const { key, tone } = describe(useReadiness());

  return (
    <section aria-labelledby="health-heading" className="card">
      <h2 id="health-heading">{t("health.heading")}</h2>
      <p role="status" className={`status status--${tone}`}>
        {t(key)}
      </p>
    </section>
  );
}
