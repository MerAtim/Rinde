import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
// Tipografías autoalojadas (ADR-0006): la CSP no permite fuentes de terceros.
import "@fontsource-variable/lexend/wght.css";
import "@fontsource-variable/google-sans-flex/opsz.css";
import "./shared/design/tokens.css";
import "./shared/design/base.css";
import "./i18n";

const container = document.getElementById("root");
if (!container) {
  throw new Error("No se encontró el elemento #root");
}

const queryClient = new QueryClient();

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
