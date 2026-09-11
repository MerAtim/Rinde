import { useTranslation } from "react-i18next";

import { isLanguage, SUPPORTED_LANGUAGES } from "../../i18n";

export function LanguageSelector() {
  const { t, i18n } = useTranslation();

  return (
    <label className="language-selector">
      <span>{t("language.label")}</span>
      <select
        value={i18n.resolvedLanguage}
        onChange={(event) => {
          if (isLanguage(event.target.value)) {
            void i18n.changeLanguage(event.target.value);
          }
        }}
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <option key={language} value={language}>
            {t(`language.${language}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
