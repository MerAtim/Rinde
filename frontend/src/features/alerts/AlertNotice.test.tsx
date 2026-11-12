import { useQueryClient } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { AlertNotice } from "./AlertNotice";
import { anAlert, aFeed } from "./fixtures";
import { alertKeys } from "./keys";

/** Como hace movimientos al guardar un gasto: vuelve a pedir las alertas. */
function Refresh() {
  const queryClient = useQueryClient();
  return (
    <button
      type="button"
      onClick={() => {
        void queryClient.invalidateQueries({ queryKey: alertKeys.all });
      }}
    >
      Guardar gasto
    </button>
  );
}

function renderAt(route: string) {
  return renderWithProviders(
    <>
      <Refresh />
      <Routes>
        <Route path="/alerts" element={<p>Pantalla de alertas</p>} />
        <Route path="*" element={<p>Otra pantalla</p>} />
      </Routes>
      <AlertNotice />
    </>,
    { route },
  );
}

const NEW_ONE = anAlert({ id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc", threshold: "over" });

describe("AlertNotice", () => {
  it("lo que ya estaba al entrar no se avisa; una alerta nueva, sí, y lleva a la lista", async () => {
    let feed = aFeed();
    const fetchMock = mockApi({ "GET /api/alerts": () => jsonResponse(200, feed) });
    renderAt("/transactions");
    const user = userEvent.setup();

    await screen.findByText("Otra pantalla");
    await waitForCalls(fetchMock, 1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    feed = aFeed({ unread: 2, alerts: [NEW_ONE, ...aFeed().alerts] });
    await user.click(screen.getByRole("button", { name: "Guardar gasto" }));

    expect(
      await screen.findByText("Supermercado llegó al tope del presupuesto"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ver" }));

    expect(await screen.findByText("Pantalla de alertas")).toBeInTheDocument();
    expect(
      screen.queryByText("Supermercado llegó al tope del presupuesto"),
    ).not.toBeInTheDocument();
  });

  it("volver a pedir sin nada nuevo no avisa", async () => {
    const fetchMock = mockApi({ "GET /api/alerts": jsonResponse(200, aFeed()) });
    renderAt("/transactions");
    const user = userEvent.setup();

    await waitForCalls(fetchMock, 1);
    await user.click(screen.getByRole("button", { name: "Guardar gasto" }));
    await waitForCalls(fetchMock, 2);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

async function waitForCalls(fetchMock: ReturnType<typeof mockApi>, count: number) {
  await screen.findByText(/pantalla/i);
  await waitFor(() => {
    expect(fetchMock.mock.calls.filter(([path]) => path === "/api/alerts")).toHaveLength(count);
  });
}
