import { useMutation } from "@tanstack/react-query";
import { Suspense } from "react";
import { useTranslation } from "react-i18next";
import { Outlet, useLocation } from "react-router";

import { logout } from "../auth/api";
import { useSetSession } from "../auth/useSession";
import { announcementFrom } from "../../shared/navigation/announcement";
import { ThemeToggle } from "../../shared/theme/ThemeToggle";
import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { cx } from "../../shared/ui/cx";
import { LanguageSelector } from "../../shared/ui/LanguageSelector";
import { type Destination, NavigationRail } from "../../shared/ui/NavigationRail";
import { TopAppBar } from "../../shared/ui/TopAppBar";
import styles from "./AppShell.module.css";

/** Marco de las pantallas con sesión: barra superior, navegación principal y contenido. */
export function AppShell() {
  const { t } = useTranslation();
  const location = useLocation();
  const setSession = useSetSession();
  const signOut = useMutation({
    mutationFn: logout,
    // Sin sesión, la ruta protegida lleva sola a la pantalla de ingreso.
    onSuccess: () => {
      setSession(null);
    },
  });

  const destinations: Destination[] = [
    { to: "/", label: t("nav.home"), icon: "home", activeIcon: "home-fill", end: true },
    { to: "/accounts", label: t("nav.accounts"), icon: "wallet", activeIcon: "wallet-fill" },
  ];

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
      <div className={cx(styles.layout)}>
        <NavigationRail label={t("nav.label")} destinations={destinations} />
        <main className={cx(styles.main)}>
          {signOut.isError ? <Alert>{t("auth.errors.NETWORK_ERROR")}</Alert> : null}
          <p role="status" className={cx(styles.announcement)}>
            {announcementFrom(location.state)}
          </p>
          <Suspense
            fallback={
              <p role="status" className={cx(styles.loading)}>
                {t("nav.loading")}
              </p>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
    </>
  );
}
