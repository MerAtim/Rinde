import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { logout } from "../auth/api";
import { useSession, useSetSession } from "../auth/useSession";
import { HealthStatus } from "../health/HealthStatus";
import { ThemeToggle } from "../../shared/theme/ThemeToggle";
import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { LanguageSelector } from "../../shared/ui/LanguageSelector";
import { TopAppBar } from "../../shared/ui/TopAppBar";
import styles from "./HomePage.module.css";

export function HomePage() {
  const { t } = useTranslation();
  const session = useSession();
  const setSession = useSetSession();
  const signOut = useMutation({
    mutationFn: logout,
    // Sin sesión, la ruta protegida lleva sola a la pantalla de ingreso.
    onSuccess: () => {
      setSession(null);
    },
  });

  return (
    <>
      <TopAppBar
        start={<span className={cx(styles.brand)}>{t("app.title")}</span>}
        end={
          <>
            <LanguageSelector />
            <ThemeToggle />
            <Button
              variant="text"
              icon="logout"
              isDisabled={signOut.isPending}
              onPress={() => {
                signOut.mutate();
              }}
            >
              {t("auth.home.logout")}
            </Button>
          </>
        }
      />
      <main className={cx(styles.main)}>
        {signOut.isError ? <Alert>{t("auth.errors.NETWORK_ERROR")}</Alert> : null}
        <section className={cx(styles.hero)}>
          <p className={cx(styles.greeting)}>
            {t("auth.home.greeting", { username: session.data?.username ?? "" })}
          </p>
          <h1 className="type-display-large">{t("app.tagline")}</h1>
          <p className={cx(styles.intro)}>{t("app.intro")}</p>
        </section>
        <HealthStatus />
      </main>
    </>
  );
}
