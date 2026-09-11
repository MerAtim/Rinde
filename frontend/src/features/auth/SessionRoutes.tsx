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

/** Pantallas de ingreso: con sesión abierta no tienen sentido, se va al inicio. */
export function RedirectIfSession() {
  const session = useSession();

  if (session.isPending) {
    return <SessionScreen state="loading" />;
  }
  if (session.data) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
