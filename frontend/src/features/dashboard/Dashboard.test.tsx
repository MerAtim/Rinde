import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import { Dashboard } from "./Dashboard";
import { aDashboard } from "./fixtures";
import { dashboardQuery } from "./period";

// jsdom no tiene canvas: se reemplaza el componente que dibuja y se conserva
// todo lo demás, incluido el nombre accesible que recibe el canvas.
vi.mock("react-chartjs-2", () => {
  const Canvas = (props: { "aria-label"?: string; role?: string }) => (
    <canvas role={props.role} aria-label={props["aria-label"]} />
  );
  return { Line: Canvas, Bar: Canvas };
});

const ACCOUNT = anAccount();
const ACCOUNTS = { "GET /api/accounts?include_archived=true": jsonResponse(200, [ACCOUNT]) };

describe("Dashboard", () => {
  it("muestra el patrimonio de hoy, la moneda de referencia y los tres bloques", async () => {
    mockApi({ ...ACCOUNTS, "GET /api/dashboard": jsonResponse(200, aDashboard()) });
    const { container } = renderWithProviders(<Dashboard />);

    const hero = await screen.findByRole("region", { name: "Patrimonio · Hoy" });
    expect(hero).toHaveTextContent("3.550.000,75");
    expect(screen.getByText(/En pesos, con el dólar MEP/)).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /patrimonio al cierre/ })).toBeInTheDocument();
    expect(
      await screen.findByRole("img", { name: /ingresos arriba del cero/ }),
    ).toBeInTheDocument();

    const spending = screen.getByRole("table", { name: /por categoría/ });
    const rows = within(spending).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Supermercado");
    expect(rows[0]).toHaveTextContent("150.300,50");
    expect(rows[1]).toHaveTextContent("Transporte");

    await expectNoA11yViolations(container);
  });

  it("cada gráfico tiene su tabla con los mismos valores", async () => {
    mockApi({ ...ACCOUNTS, "GET /api/dashboard": jsonResponse(200, aDashboard()) });
    renderWithProviders(<Dashboard />);
    const user = userEvent.setup();

    const netWorth = await screen.findByRole("region", { name: "Patrimonio" });
    await user.click(within(netWorth).getByRole("radio", { name: "Tabla" }));
    const closings = within(netWorth).getByRole("table");
    // Un cierre sin cotización lo dice: no se muestra un cero inventado.
    expect(within(closings).getByRole("row", { name: /octubre de 2026/ })).toHaveTextContent(
      "Sin cotización",
    );
    expect(within(netWorth).queryByRole("img")).not.toBeInTheDocument();

    const flow = screen.getByRole("region", { name: "Ingresos y gastos" });
    await user.click(within(flow).getByRole("radio", { name: "Tabla" }));
    const october = within(flow).getByRole("row", { name: /octubre de 2026/ });
    // El neto negativo se lee como gasto: con la palabra, no solo con el color.
    expect(october).toHaveTextContent("Gasto");
    expect(october).toHaveTextContent("50.000,00");
  });

  it("lo que no se pudo convertir sale aparte, en su moneda", async () => {
    mockApi({ ...ACCOUNTS, "GET /api/dashboard": jsonResponse(200, aDashboard()) });
    renderWithProviders(<Dashboard />);

    const section = await screen.findByRole("region", { name: "Fuera de los totales" });
    expect(within(section).getByRole("columnheader", { name: "BTC" })).toBeInTheDocument();
    expect(within(section).getByRole("row", { name: /Saldo/ })).toHaveTextContent("0,01250000");
  });

  it("sin cotización de hoy, el patrimonio lo dice en vez de mostrar un número", async () => {
    const data = aDashboard();
    const closings = data.net_worth.map((point) => ({ ...point, total: null }));
    mockApi({
      ...ACCOUNTS,
      "GET /api/dashboard": jsonResponse(200, { ...data, net_worth: closings }),
    });
    renderWithProviders(<Dashboard />);

    expect(await screen.findByText(/Falta la cotización de hoy/)).toBeInTheDocument();
  });

  it("sin gastos en el período, lo explica", async () => {
    mockApi({ ...ACCOUNTS, "GET /api/dashboard": jsonResponse(200, aDashboard({ spending: [] })) });
    renderWithProviders(<Dashboard />);

    expect(await screen.findByText("No hubo gastos en este período.")).toBeInTheDocument();
  });

  it("toma de la URL el período y la cuenta", async () => {
    const query = dashboardQuery({ months: 12, accountId: ACCOUNT.id }, new Date());
    const fetch = mockApi({
      ...ACCOUNTS,
      [`GET /api/dashboard?from=${query.from ?? ""}&account=${ACCOUNT.id}`]: jsonResponse(
        200,
        aDashboard(),
      ),
    });
    renderWithProviders(<Dashboard />, { route: `/?months=12&account=${ACCOUNT.id}` });

    await screen.findByRole("region", { name: "Patrimonio · Hoy" });
    expect(screen.getByRole("button", { name: /Período/ })).toHaveTextContent("Últimos 12 meses");
    expect(fetch).toHaveBeenCalledWith(
      `/api/dashboard?from=${query.from ?? ""}&account=${ACCOUNT.id}`,
      expect.anything(),
    );
  });

  it("un filtro de la URL que no vale no llega al servidor", async () => {
    const fetch = mockApi({
      ...ACCOUNTS,
      "GET /api/dashboard": jsonResponse(200, aDashboard()),
    });
    renderWithProviders(<Dashboard />, { route: "/?months=1000&account=x%27%20OR%201%3D1" });

    await screen.findByRole("region", { name: "Patrimonio · Hoy" });
    expect(fetch).toHaveBeenCalledWith("/api/dashboard", expect.anything());
  });

  it("al elegir otro período, pide ese período", async () => {
    const query = dashboardQuery({ months: 3, accountId: "" }, new Date());
    const fetch = mockApi({
      ...ACCOUNTS,
      "GET /api/dashboard": jsonResponse(200, aDashboard()),
      [`GET /api/dashboard?from=${query.from ?? ""}`]: jsonResponse(200, aDashboard()),
    });
    renderWithProviders(<Dashboard />);
    const user = userEvent.setup();

    await screen.findByRole("region", { name: "Patrimonio · Hoy" });
    await user.click(screen.getByRole("button", { name: /Período/ }));
    await user.click(await screen.findByRole("option", { name: "Últimos 3 meses" }));

    await vi.waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        `/api/dashboard?from=${query.from ?? ""}`,
        expect.anything(),
      );
    });
  });

  it("sin cuentas, invita a abrir la primera", async () => {
    mockApi({
      "GET /api/accounts?include_archived=true": jsonResponse(200, []),
      "GET /api/dashboard": jsonResponse(200, aDashboard()),
    });
    renderWithProviders(<Dashboard />);

    expect(
      await screen.findByRole("heading", { name: "Todavía no hay nada que resumir" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir una cuenta" })).toHaveAttribute(
      "href",
      "/accounts/new",
    );
  });

  it("un error se explica con su código traducido y se puede reintentar", async () => {
    mockApi({
      ...ACCOUNTS,
      "GET /api/dashboard": jsonResponse(422, { code: "DASHBOARD_PERIOD_INVALID" }),
    });
    renderWithProviders(<Dashboard />);

    expect(
      await screen.findByText("Ese período no se puede mostrar. Elegí otro."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("en inglés, todo el texto cambia de idioma", async () => {
    const { default: i18n } = await import("../../i18n");
    await i18n.changeLanguage("en");
    mockApi({ ...ACCOUNTS, "GET /api/dashboard": jsonResponse(200, aDashboard()) });
    renderWithProviders(<Dashboard />);

    expect(await screen.findByRole("heading", { level: 1, name: "Overview" })).toBeInTheDocument();
    expect(await screen.findByText(/In pesos, at the MEP dollar rate/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Net worth · Today" })).toHaveTextContent(
      "3,550,000.75",
    );
  });
});
