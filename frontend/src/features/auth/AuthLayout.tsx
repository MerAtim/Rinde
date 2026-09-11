import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ThemeToggle } from "../../shared/theme/ThemeToggle";
import { cx } from "../../shared/ui/cx";
import { LanguageSelector } from "../../shared/ui/LanguageSelector";
import styles from "./AuthLayout.module.css";

const DAYS = Array.from({ length: 30 }, (_, index) => index + 1);

function dayState(day: number): "past" | "covered" | "gap" {
  if (day <= 10) {
    return "past";
  }
  return day <= 24 ? "covered" : "gap";
}

/** Marco de las pantallas de cuenta: la marca a un lado y el formulario, sin distracciones, al otro. */
export function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();

  return (
    <div className={cx(styles.layout)}>
      <aside className={cx(styles.brand)} aria-label={t("auth.brand.label")}>
        <span className={cx(styles.brandName)}>{t("app.title")}</span>
        <div className={cx(styles.brandBody)}>
          <p className={cx(styles.headline)}>{t("app.tagline")}</p>
          <div className={cx(styles.runway)} aria-hidden="true">
            {DAYS.map((day) => (
              <span key={day} className={cx(styles.cell)} data-state={dayState(day)} />
            ))}
          </div>
          <ul className={cx(styles.points)}>
            <li>{t("auth.brand.privacy")}</li>
            <li>{t("auth.brand.security")}</li>
            <li>{t("auth.brand.currencies")}</li>
          </ul>
        </div>
        <span className={cx(styles.footnote)}>{t("auth.brand.footnote")}</span>
      </aside>
      <div className={cx(styles.content)}>
        <header className={cx(styles.toolbar)}>
          <span className={cx(styles.compactBrand)}>{t("app.title")}</span>
          <div className={cx(styles.tools)}>
            <LanguageSelector />
            <ThemeToggle />
          </div>
        </header>
        <main className={cx(styles.main)}>{children}</main>
      </div>
    </div>
  );
}
