import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router";

import { LoginPage } from "./features/auth/LoginPage";
import { RecoverPage } from "./features/auth/RecoverPage";
import { RecoveryCodePage } from "./features/auth/RecoveryCodePage";
import { RedirectIfSession, RequireSession } from "./features/auth/SessionRoutes";
import { SignupPage } from "./features/auth/SignupPage";
import { HomePage } from "./features/home/HomePage";
import { AppShell } from "./features/shell/AppShell";

// Cuentas se descarga recién al entrar: el ingreso y el inicio no pagan por sus
// diálogos y formularios. El marco muestra la espera (Suspense en AppShell).
const AccountsPage = lazy(() =>
  import("./features/accounts/AccountsPage").then((module) => ({ default: module.AccountsPage })),
);
const NewAccountPage = lazy(() =>
  import("./features/accounts/NewAccountPage").then((module) => ({
    default: module.NewAccountPage,
  })),
);
const AccountPage = lazy(() =>
  import("./features/accounts/AccountPage").then((module) => ({ default: module.AccountPage })),
);

export function App() {
  return (
    <Routes>
      <Route element={<RequireSession />}>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="accounts" element={<AccountsPage />} />
          <Route path="accounts/new" element={<NewAccountPage />} />
          <Route path="accounts/:accountId" element={<AccountPage />} />
        </Route>
      </Route>
      <Route element={<RedirectIfSession />}>
        <Route path="login" element={<LoginPage />} />
        <Route path="signup" element={<SignupPage />} />
        <Route path="recover" element={<RecoverPage />} />
      </Route>
      <Route path="recovery-code" element={<RecoveryCodePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
