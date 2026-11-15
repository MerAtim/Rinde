import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { startDemo } from "./api";
import styles from "./AuthForm.module.css";
import { errorCodeOf } from "./errors";
import { useSetSession } from "./useSession";

/** Entrar sin registrarse, a una demo propia con datos de ejemplo (ADR-0028). */
export function DemoStart() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setSession = useSetSession();
  const demo = useMutation({
    mutationFn: startDemo,
    // La respuesta trae lo mismo que /me: no hace falta otra vuelta al servidor.
    // Una demo puede seguir en las pantallas de ingreso, así que se va al inicio a mano.
    onSuccess: (session) => {
      setSession(session);
      void navigate("/", { replace: true });
    },
  });

  const code = errorCodeOf(demo.error);
  // El límite de la demo es otro que el de los intentos fallidos: su propio texto.
  const message =
    code === "TOO_MANY_ATTEMPTS" ? t("auth.demo.tooMany") : code ? t(`auth.errors.${code}`) : null;

  return (
    <div className={cx(styles.demo)}>
      <p className={cx(styles.footer)}>{t("auth.demo.lead")}</p>
      {message ? <Alert>{message}</Alert> : null}
      <Button
        variant="outlined"
        isDisabled={demo.isPending}
        onPress={() => {
          demo.mutate();
        }}
      >
        {demo.isPending ? t("auth.demo.starting") : t("auth.demo.start")}
      </Button>
      <p className={cx(styles.note)}>{t("auth.demo.note")}</p>
    </div>
  );
}
