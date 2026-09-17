import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { type Destination, NavigationRail } from "./NavigationRail";

const DESTINATIONS: Destination[] = [
  { to: "/", label: "Inicio", icon: "home", activeIcon: "home-fill", end: true },
  { to: "/accounts", label: "Cuentas", icon: "wallet", activeIcon: "wallet-fill" },
];

function renderAt(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <NavigationRail label="Principal" destinations={DESTINATIONS} />
      <Routes>
        <Route index element={<h1>Pantalla de inicio</h1>} />
        <Route path="accounts/*" element={<h1>Pantalla de cuentas</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("NavigationRail", () => {
  it("marca el destino actual, también en sus pantallas internas", () => {
    renderAt("/accounts/new");

    expect(screen.getByRole("link", { name: "Cuentas" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Inicio" })).not.toHaveAttribute("aria-current");
  });

  it("lleva al destino elegido", async () => {
    const user = userEvent.setup();
    renderAt("/");

    await user.click(screen.getByRole("link", { name: "Cuentas" }));

    expect(screen.getByRole("heading", { name: "Pantalla de cuentas" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cuentas" })).toHaveAttribute("aria-current", "page");
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = renderAt("/");

    await expectNoA11yViolations(container);
  });
});
