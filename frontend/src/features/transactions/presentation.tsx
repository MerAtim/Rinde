import { useTranslation } from "react-i18next";

import type { Category } from "./api";

/** Hoy en la zona horaria de quien carga, no en UTC: si no, a la noche adelanta un día. */
export function today(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${String(now.getFullYear())}-${month}-${day}`;
}

/** El nombre de una categoría: las sembradas se traducen por su identificador. */
export function useCategoryName(): (category: Category) => string {
  const { t } = useTranslation();
  return (category) =>
    category.slug ? t(`transactions.seed.${category.slug}`, category.name) : category.name;
}
