import { useTranslation } from "react-i18next";

import { useLocalTimeFormatter } from "../../i18n/format";
import { LinkButton } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { Icon } from "../../shared/ui/Icon";
import styles from "./DemoBanner.module.css";

/**
 * Aviso fijo de una demo: que los datos son de ejemplo y a qué hora se borran
 * (ADR-0028). No se cierra: quien carga algo tiene que saberlo siempre. Crear
 * una cuenta lleva al registro, y la sesión nueva reemplaza a la de la demo.
 */
export function DemoBanner({ expiresAt }: { expiresAt: string }) {
  const { t } = useTranslation();
  const formatTime = useLocalTimeFormatter();

  return (
    <section className={cx(styles.banner)} aria-label={t("auth.demo.label")}>
      <Icon name="schedule" size={20} />
      <p className={cx(styles.text)}>{t("auth.demo.banner", { time: formatTime(expiresAt) })}</p>
      <LinkButton to="/signup" variant="text">
        {t("auth.demo.createAccount")}
      </LinkButton>
    </section>
  );
}
