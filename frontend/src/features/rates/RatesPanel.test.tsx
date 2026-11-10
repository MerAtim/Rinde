import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../../App";
import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { aQuote } from "./fixtures";

const SESSION = { "GET /api/auth/me": jsonResponse(200, { username: "mechi" }) };

// Un feriado, el oficial de "hoy" es el del jueves: la fila lo tiene que decir.
const OFFICIAL = aQuote({
  rate_type: "official",
  buy: "1520.00000000",
  sell: "1570.00000000",
  updated_at: "2026-11-05T18:55:00Z",
});
const MEP = aQuote();
const BLUE = aQuote({
  rate_type: "blue",
  buy: "1535.00000000",
  sell: "1555.00000000",
  source: "criptoya",
});

describe("Dólar hoy", () => {
  it("muestra cada dólar con compra y venta en una tabla", async () => {
    mockApi({ ...SESSION, "GET /api/rates": jsonResponse(200, [OFFICIAL, MEP, BLUE]) });
    const { container } = renderWithProviders(<App />);

    const table = await screen.findByRole("table");
    const mep = within(table).getByRole("row", { name: /MEP/ });
    expect(within(mep).getByRole("cell", { name: /1\.560,20/ })).toBeInTheDocument();
    expect(within(mep).getByRole("cell", { name: /1\.587,90/ })).toBeInTheDocument();
    expect(within(mep).getByText("DolarAPI")).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Compra" })).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("avisa de qué día es una cotización que no se actualizó hoy", async () => {
    mockApi({ ...SESSION, "GET /api/rates": jsonResponse(200, [OFFICIAL, BLUE]) });
    renderWithProviders(<App />);

    const official = await screen.findByRole("row", { name: /Oficial/ });
    expect(
      within(official).getByText(/^DolarAPI, actualizado el 5 de noviembre/),
    ).toBeInTheDocument();
    const blue = screen.getByRole("row", { name: /Blue/ });
    expect(within(blue).getByText("CriptoYa")).toBeInTheDocument();
  });

  it("explica cuando ninguna fuente publicó nada", async () => {
    mockApi({ ...SESSION, "GET /api/rates": jsonResponse(200, []) });
    renderWithProviders(<App />);

    expect(await screen.findByText("Hoy ninguna fuente publicó cotizaciones.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("distingue las fuentes caídas de un error propio", async () => {
    mockApi({
      ...SESSION,
      "GET /api/rates": jsonResponse(503, { code: "RATES_UNAVAILABLE" }),
    });
    renderWithProviders(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Las fuentes de cotizaciones no responden",
    );
  });

  it("muestra un error genérico si falla otra cosa", async () => {
    mockApi({ ...SESSION, "GET /api/rates": jsonResponse(500, {}) });
    renderWithProviders(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudieron traer las cotizaciones.",
    );
  });

  it("avisa mientras consulta", async () => {
    mockApi({ ...SESSION, "GET /api/rates": () => new Promise<Response>(() => undefined) });
    renderWithProviders(<App />);

    expect(await screen.findByText("Consultando cotizaciones…")).toBeInTheDocument();
  });
});
