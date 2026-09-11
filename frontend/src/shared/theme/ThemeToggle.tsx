import { useTranslation } from "react-i18next";

import { IconButton } from "../ui/IconButton";
import { useTheme } from "./useTheme";

/** Alterna entre oscuro (por defecto) y claro. La etiqueta dice lo que va a pasar. */
export function ThemeToggle() {
  const { t } = useTranslation();
  const [theme, setTheme] = useTheme();
  const isDark = theme === "dark";

  return (
    <IconButton
      icon={isDark ? "light-mode" : "dark-mode"}
      label={t(isDark ? "theme.toLight" : "theme.toDark")}
      onPress={() => {
        setTheme(isDark ? "light" : "dark");
      }}
    />
  );
}
