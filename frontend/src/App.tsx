import { Navigate, Route, Routes } from "react-router";

import { LoginPage } from "./features/auth/LoginPage";
import { RecoverPage } from "./features/auth/RecoverPage";
import { RecoveryCodePage } from "./features/auth/RecoveryCodePage";
import { RedirectIfSession, RequireSession } from "./features/auth/SessionRoutes";
import { SignupPage } from "./features/auth/SignupPage";
import { HomePage } from "./features/home/HomePage";
import { AppShell } from "./features/shell/AppShell";

export function App() {
  return (
    <Routes>
      <Route element={<RequireSession />}>
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
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
