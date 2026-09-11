import { useTranslation } from "react-i18next";

import { HealthStatus } from "./features/health/HealthStatus";
import { LanguageSelector } from "./shared/ui/LanguageSelector";

export function App() {
  const { t } = useTranslation();

  return (
    <>
      <header className="app-header">
        <div>
          <h1>{t("app.title")}</h1>
          <p className="tagline">{t("app.tagline")}</p>
        </div>
        <LanguageSelector />
      </header>
      <main className="app-main">
        <HealthStatus />
      </main>
    </>
  );
}
