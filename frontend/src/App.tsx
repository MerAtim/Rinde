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
const TransactionsPage = lazy(() =>
  import("./features/transactions/TransactionsPage").then((module) => ({
    default: module.TransactionsPage,
  })),
);
const NewTransactionPage = lazy(() =>
  import("./features/transactions/NewTransactionPage").then((module) => ({
    default: module.NewTransactionPage,
  })),
);
const NewTransferPage = lazy(() =>
  import("./features/transfers/NewTransferPage").then((module) => ({
    default: module.NewTransferPage,
  })),
);
const PreferencesPage = lazy(() =>
  import("./features/preferences/PreferencesPage").then((m) => ({ default: m.PreferencesPage })),
);
const BudgetsPage = lazy(() =>
  import("./features/budgets/BudgetsPage").then((module) => ({ default: module.BudgetsPage })),
);
const BudgetFormPage = lazy(() =>
  import("./features/budgets/BudgetFormPage").then((module) => ({
    default: module.BudgetFormPage,
  })),
);
const AlertsPage = lazy(() =>
  import("./features/alerts/AlertsPage").then((module) => ({ default: module.AlertsPage })),
);
const EditTransactionPage = lazy(() =>
  import("./features/transactions/EditTransactionPage").then((module) => ({
    default: module.EditTransactionPage,
  })),
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
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="transactions/new" element={<NewTransactionPage />} />
          <Route path="transactions/:transactionId" element={<EditTransactionPage />} />
          <Route path="transfers/new" element={<NewTransferPage />} />
          <Route path="budgets" element={<BudgetsPage />} />
          <Route path="budgets/new" element={<BudgetFormPage />} />
          <Route path="budgets/:categoryId/edit" element={<BudgetFormPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="preferences" element={<PreferencesPage />} />
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
