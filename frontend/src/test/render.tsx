import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";

import { createQueryClient } from "../queryClient";

interface RenderOptions {
  /** Ruta inicial, para probar pantallas y redirecciones. */
  route?: string;
}

/** Renderiza con el cliente de datos de la app, sin reintentos, y un router en memoria. */
export function renderWithProviders(ui: ReactElement, { route = "/" }: RenderOptions = {}) {
  const client = createQueryClient({ queries: { retry: false }, mutations: { retry: false } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

export function jsonResponse(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
