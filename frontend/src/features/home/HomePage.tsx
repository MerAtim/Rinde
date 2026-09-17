import { useTranslation } from "react-i18next";

import { useSession } from "../auth/useSession";
import { HealthStatus } from "../health/HealthStatus";
import { cx } from "../../shared/ui/cx";
import styles from "./HomePage.module.css";

export function HomePage() {
  const { t } = useTranslation();
  const session = useSession();

  return (
    <div className={cx(styles.page)}>
      <section className={cx(styles.hero)}>
        <p className={cx(styles.greeting)}>
          {t("auth.home.greeting", { username: session.data?.username ?? "" })}
        </p>
        <h1 className="type-display-large">{t("app.tagline")}</h1>
        <p className={cx(styles.intro)}>{t("app.intro")}</p>
      </section>
      <HealthStatus />
    </div>
  );
}
