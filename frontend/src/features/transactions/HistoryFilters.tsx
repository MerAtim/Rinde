import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { Select } from "../../shared/ui/Select";
import { TextField } from "../../shared/ui/TextField";
import type { Category } from "./api";
import { useCategoryName } from "./presentation";
import styles from "./Transactions.module.css";

export interface HistoryFilterValues {
  categoryId: string;
  text: string;
}

interface HistoryFiltersProps {
  categories: Category[];
  values: HistoryFilterValues;
  onChange: (values: HistoryFilterValues) => void;
}

/**
 * Los filtros de la lista.
 *
 * El texto no busca mientras se escribe: espera a que la persona pare. Sin eso,
 * "panadería" son nueve pedidos al servidor y ocho listas que aparecen y
 * desaparecen mientras todavía está escribiendo.
 */
const PAUSA_MS = 300;

export function HistoryFilters({ categories, values, onChange }: HistoryFiltersProps) {
  const { t } = useTranslation();
  const categoryName = useCategoryName();
  const [text, setText] = useState(values.text);
  const [textoDeLaUrl, setTextoDeLaUrl] = useState(values.text);

  // La URL manda: si cambia desde afuera, el campo la sigue. Se ajusta durante
  // el render y no en un efecto, que es lo que recomienda React: así no hay un
  // pintado intermedio con el valor viejo.
  if (values.text !== textoDeLaUrl) {
    setTextoDeLaUrl(values.text);
    setText(values.text);
  }

  useEffect(() => {
    if (text === values.text) {
      return;
    }
    const espera = setTimeout(() => {
      onChange({ ...values, text });
    }, PAUSA_MS);
    return () => {
      clearTimeout(espera);
    };
  }, [text, values, onChange]);

  const hasFilters = values.categoryId !== "" || values.text !== "";

  return (
    <div className={cx(styles.filters)} role="search">
      <TextField
        label={t("transactions.filters.text")}
        value={text}
        onChange={setText}
        type="search"
        autoComplete="off"
        validationBehavior="aria"
      />
      <Select
        label={t("transactions.filters.category")}
        placeholder={t("transactions.filters.allCategories")}
        options={[
          { id: "", label: t("transactions.filters.allCategories") },
          ...categories.map((row) => ({ id: row.id, label: categoryName(row) })),
        ]}
        value={values.categoryId || ""}
        onChange={(categoryId) => {
          onChange({ ...values, categoryId });
        }}
      />
      {hasFilters ? (
        <Button
          variant="text"
          onPress={() => {
            onChange({ categoryId: "", text: "" });
          }}
        >
          {t("transactions.filters.clear")}
        </Button>
      ) : null}
    </div>
  );
}
