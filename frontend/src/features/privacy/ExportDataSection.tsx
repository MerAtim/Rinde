import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { saveFile } from "../../shared/files/saveFile";
import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { downloadPersonalData, isPrivacyApiError } from "./api";
import styles from "./ExportDataSection.module.css";

/**
 * Descargar todos los datos propios (Ley 25.326, art. 14; ADR-0034). Es una
 * mutación y no una consulta: el archivo no se guarda en la caché, y si la
 * sesión venció, el cliente de datos lleva a ingresar como en cualquier pedido.
 */
export function ExportDataSection() {
  const { t } = useTranslation();
  const download = useMutation({
    mutationFn: downloadPersonalData,
    onSuccess: (file) => {
      saveFile(file.name, file.content);
    },
  });
  const code = download.error
    ? isPrivacyApiError(download.error)
      ? download.error.code
      : "UNKNOWN_ERROR"
    : null;

  return (
    <section className={cx(styles.section)} aria-labelledby="export-data-title">
      <h2 id="export-data-title" className={cx(styles.title)}>
        {t("account.export.title")}
      </h2>
      <p className={cx(styles.text)}>{t("account.export.description")}</p>
      {code && code !== "NOT_AUTHENTICATED" ? (
        <Alert>{t(`account.export.errors.${code}`)}</Alert>
      ) : null}
      <div>
        <Button
          variant="outlined"
          icon="download"
          isDisabled={download.isPending}
          onPress={() => {
            download.mutate();
          }}
        >
          {download.isPending ? t("account.export.downloading") : t("account.export.download")}
        </Button>
      </div>
      {download.isSuccess ? (
        <p role="status" className={cx(styles.text)}>
          {t("account.export.done")}
        </p>
      ) : null}
    </section>
  );
}
