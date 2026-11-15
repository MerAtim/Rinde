import { Navigate, Outlet } from "react-router";

import { SessionScreen } from "./SessionScreen";
import { useSession } from "./useSession";

/** Pantallas que requieren sesión: sin ella, se va a ingresar. */
export function RequireSession() {
  const session = useSession();

  if (session.isPending) {
    return <SessionScreen state="loading" />;
  }
  if (session.isError) {
    return (
      <SessionScreen
        state="error"
        onRetry={() => {
          void session.refetch();
        }}
      />
    );
  }
  if (session.data === null) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

/**
 * Pantallas de ingreso: con sesión abierta no tienen sentido, se va al inicio.
 * Salvo en una demo, que no es la cuenta de nadie: desde ella se puede crear la
 * propia o ingresar, y la sesión nueva reemplaza a la de la demo (ADR-0028).
 */
export function RedirectIfSession() {
  const session = useSession();

  if (session.isPending) {
    return <SessionScreen state="loading" />;
  }
  const isDemo = Boolean(session.data?.demo_expires_at);
  if (session.data && !isDemo) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
