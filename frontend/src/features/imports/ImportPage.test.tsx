import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { mockApi } from "../../test/api";
import { jsonResponse, renderWithProviders } from "../../test/render";
import { anAccount } from "../accounts/fixtures";
import { MAX_FILE_BYTES } from "./api";
import { aBatch } from "./fixtures";
import { ImportPage } from "./ImportPage";

const ACCOUNT = anAccount();

// Como lo exporta Excel en español: punto y coma, tildes en Windows-1252, débito y crédito.
const EXCEL = new Uint8Array([
  ...new TextEncoder().encode("Fecha;Descripci"),
  0xf3,
  ...new TextEncoder().encode("n;D"),
  0xe9,
  ...new TextEncoder().encode("bito;Cr"),
  0xe9,
  ...new TextEncoder().encode("dito\n03/11/2026;PANADER"),
  0xcd,
  ...new TextEncoder().encode("A;1.500,00;\n"),
]);

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/transactions/import" element={<ImportPage />} />
      <Route path="/imports/:batchId" element={<p>Vista previa</p>} />
    </Routes>,
    { route: "/transactions/import" },
  );
}

function fileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) {
    throw new Error("no hay campo de archivo");
  }
  return input;
}

function sentForm(fetchMock: ReturnType<typeof mockApi>): FormData | undefined {
  const body = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.body;
  return body instanceof FormData ? body : undefined;
}

describe("ImportPage", () => {
  it("lee las primeras filas, propone columnas y sube el archivo con el formato elegido", async () => {
    const fetchMock = mockApi({
      "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
      "POST /api/imports": jsonResponse(201, aBatch()),
    });
    const { container } = renderPage();
    const user = userEvent.setup();

    expect(
      await screen.findByRole("heading", { level: 1, name: "Importar movimientos" }),
    ).toBeInTheDocument();
    await screen.findByRole("button", { name: "Ver la vista previa" });
    // Con una sola cuenta, ya viene elegida.
    expect(screen.getByRole("button", { name: /Cuenta/ })).toHaveTextContent(
      "Galicia sueldo (ARS)",
    );
    await user.upload(fileInput(container), new File([EXCEL], "octubre.csv", { type: "text/csv" }));

    // En UTF-8 las tildes de Excel no se leen: lo dice y no adivina.
    expect(await screen.findByText(/no se puede leer como UTF-8/)).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Excel en español" }));

    const sample = await screen.findByRole("region", { name: "Primeras filas del archivo" });
    expect(within(sample).getByRole("columnheader", { name: "Descripción" })).toBeInTheDocument();
    expect(within(sample).getByRole("cell", { name: "PANADERÍA" })).toBeInTheDocument();
    // Los títulos proponen las columnas, a la vista para cambiarlas.
    expect(screen.getByRole("radio", { name: "Débito y crédito" })).toBeChecked();
    expect(screen.getByRole("button", { name: /Débito$/ })).toHaveTextContent("Columna 3: Débito");
    await expectNoA11yViolations(container);

    await user.click(screen.getByRole("button", { name: "Ver la vista previa" }));

    expect(await screen.findByText("Vista previa")).toBeInTheDocument();
    const form = sentForm(fetchMock);
    expect(form?.get("account_id")).toBe(ACCOUNT.id);
    expect(form?.get("format")).toBe("csv");
    expect(JSON.parse(form?.get("layout") as string)).toEqual({
      delimiter: ";",
      encoding: "windows-1252",
      decimal_mark: "comma",
      date_order: "dmy",
      has_header: true,
      date_column: 0,
      description_column: 1,
      amount: { kind: "debit_credit", debit: 2, credit: 3 },
    });
    expect((form?.get("file") as File | null)?.name).toBe("octubre.csv");
  });

  it("sin cuenta ni archivo no envía nada", async () => {
    const fetchMock = mockApi({
      "GET /api/accounts": jsonResponse(200, [ACCOUNT, anAccount({ id: "otra", name: "Macro" })]),
    });
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Ver la vista previa" }));
    expect(screen.getByText("Elegí la cuenta donde entran los movimientos.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Cuenta/ }));
    await user.click(await screen.findByRole("option", { name: "Macro (ARS)" }));
    await user.click(screen.getByRole("button", { name: "Ver la vista previa" }));
    expect(screen.getByText("Elegí un archivo.")).toBeInTheDocument();
    expect(sentForm(fetchMock)).toBeUndefined();
  });

  it("sin columnas elegidas lo dice antes de subir", async () => {
    const fetchMock = mockApi({ "GET /api/accounts": jsonResponse(200, [ACCOUNT]) });
    const { container } = renderPage();
    const user = userEvent.setup();

    await screen.findByRole("button", { name: "Ver la vista previa" });
    await user.upload(
      fileInput(container),
      new File(["15/10/2026;COTO;-10,00\n"], "sin-titulos.csv", { type: "text/csv" }),
    );
    await user.click(await screen.findByRole("checkbox", { name: /primera fila/ }));
    await user.click(screen.getByRole("button", { name: "Ver la vista previa" }));

    expect(
      screen.getByText("Elegí las columnas de la fecha, la descripción y el monto."),
    ).toBeInTheDocument();
    expect(sentForm(fetchMock)).toBeUndefined();
  });

  it("un archivo de más de 1 MB se avisa sin subirlo", async () => {
    const fetchMock = mockApi({ "GET /api/accounts": jsonResponse(200, [ACCOUNT]) });
    const { container } = renderPage();
    const user = userEvent.setup();

    await screen.findByRole("button", { name: "Ver la vista previa" });
    await user.upload(
      fileInput(container),
      new File([new Uint8Array(MAX_FILE_BYTES + 1)], "enorme.csv", { type: "text/csv" }),
    );

    expect(await screen.findByText(/pasa de 1 MB/)).toBeInTheDocument();
    expect(sentForm(fetchMock)).toBeUndefined();
  });

  it("muestra el error del servidor", async () => {
    mockApi({
      "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
      "POST /api/imports": jsonResponse(422, { code: "IMPORT_NOTHING_READABLE" }),
    });
    const { container } = renderPage();
    const user = userEvent.setup();

    await screen.findByRole("button", { name: "Ver la vista previa" });
    await user.upload(
      fileInput(container),
      new File(["Fecha;Detalle;Importe\n15/10/2026;COTO;-10,00\n"], "a.csv", { type: "text/csv" }),
    );
    await screen.findByRole("region", { name: "Primeras filas del archivo" });
    await user.click(screen.getByRole("button", { name: "Ver la vista previa" }));

    expect(await screen.findByText(/No pudimos leer ninguna línea/)).toBeInTheDocument();
  });
  describe("resumen PDF de Macro", () => {
    const PDF = new File(["%PDF-1.4"], "resumen.pdf", { type: "application/pdf" });

    it("se sube sin formato: el del PDF es fijo", async () => {
      const fetchMock = mockApi({
        "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
        "POST /api/imports": jsonResponse(201, aBatch()),
      });
      const { container } = renderPage();
      const user = userEvent.setup();

      await screen.findByRole("button", { name: "Ver la vista previa" });
      expect(screen.getByRole("group", { name: "Cómo está escrito" })).toBeInTheDocument();
      await user.click(screen.getByRole("radio", { name: "Resumen PDF de Macro" }));

      expect(screen.queryByRole("group", { name: "Cómo está escrito" })).not.toBeInTheDocument();
      expect(screen.getByText(/lo controlamos con sus saldos y totales/)).toBeInTheDocument();
      await user.upload(fileInput(container), PDF);
      expect(screen.getByText("resumen.pdf")).toBeInTheDocument();
      await expectNoA11yViolations(container);

      await user.click(screen.getByRole("button", { name: "Ver la vista previa" }));

      expect(await screen.findByText("Vista previa")).toBeInTheDocument();
      const form = sentForm(fetchMock);
      expect(form?.get("format")).toBe("macro_pdf");
      expect(form?.has("layout")).toBe(false);
      expect((form?.get("file") as File | null)?.name).toBe("resumen.pdf");
    });

    it("cambiar el tipo de archivo suelta el elegido", async () => {
      mockApi({ "GET /api/accounts": jsonResponse(200, [ACCOUNT]) });
      const { container } = renderPage();
      const user = userEvent.setup();

      await screen.findByRole("button", { name: "Ver la vista previa" });
      await user.upload(
        fileInput(container),
        new File([EXCEL], "octubre.csv", { type: "text/csv" }),
      );
      await user.click(screen.getByRole("radio", { name: "Resumen PDF de Macro" }));

      expect(screen.queryByText("octubre.csv")).not.toBeInTheDocument();
      expect(fileInput(container).accept).toContain(".pdf");
      await user.click(screen.getByRole("button", { name: "Ver la vista previa" }));
      expect(await screen.findByText("Elegí un archivo.")).toBeInTheDocument();
    });

    it("un resumen que no cierra no importa nada y lo dice", async () => {
      mockApi({
        "GET /api/accounts": jsonResponse(200, [ACCOUNT]),
        "POST /api/imports": jsonResponse(422, { code: "IMPORT_STATEMENT_UNBALANCED" }),
      });
      const { container } = renderPage();
      const user = userEvent.setup();

      await screen.findByRole("button", { name: "Ver la vista previa" });
      await user.click(screen.getByRole("radio", { name: "Resumen PDF de Macro" }));
      await user.upload(fileInput(container), PDF);
      await user.click(screen.getByRole("button", { name: "Ver la vista previa" }));

      expect(await screen.findByText(/no cierra con los saldos y totales/)).toBeInTheDocument();
    });
  });
});
