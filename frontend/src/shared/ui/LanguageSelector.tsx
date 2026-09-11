import { useTranslation } from "react-i18next";

import { isLanguage, type Language, SUPPORTED_LANGUAGES } from "../../i18n";
import { SegmentedButton } from "./SegmentedButton";

export function LanguageSelector() {
  const { t, i18n } = useTranslation();
  const resolved = i18n.resolvedLanguage ?? null;
  const current: Language = isLanguage(resolved) ? resolved : "es";

  return (
    <SegmentedButton
      label={t("language.label")}
      value={current}
      options={SUPPORTED_LANGUAGES.map((language) => ({
        id: language,
        label: t(`language.short.${language}`),
        accessibleLabel: t(`language.${language}`),
      }))}
      onChange={(language) => {
        void i18n.changeLanguage(language);
      }}
    />
  );
}
