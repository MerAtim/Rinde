import { useTranslation } from "react-i18next";

import styles from "./App.module.css";
import { HealthStatus } from "./features/health/HealthStatus";
import { ThemeToggle } from "./shared/theme/ThemeToggle";
import { cx } from "./shared/ui/cx";
import { LanguageSelector } from "./shared/ui/LanguageSelector";
import { TopAppBar } from "./shared/ui/TopAppBar";

export function App() {
  const { t } = useTranslation();

  return (
    <>
      <TopAppBar
        start={<span className={cx(styles.brand)}>{t("app.title")}</span>}
        end={
          <>
            <LanguageSelector />
            <ThemeToggle />
          </>
        }
      />
      <main className={cx(styles.main)}>
        <section className={cx(styles.hero)}>
          <h1 className="type-display-large">{t("app.tagline")}</h1>
          <p className={cx(styles.intro)}>{t("app.intro")}</p>
        </section>
        <HealthStatus />
      </main>
    </>
  );
}
