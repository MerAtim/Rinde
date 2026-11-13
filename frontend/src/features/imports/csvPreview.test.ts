import { describe, expect, it } from "vitest";

import { decode, previewRows } from "./csvPreview";

describe("previewRows", () => {
  it("lee comillas, separadores adentro y saltos de línea", () => {
    const text =
      'Fecha;Detalle;Importe\r\n15/10/2026;"TRANSF; de ""Ana""";-1.500,00\n\n16/10/2026;"dos\nlíneas";2\n';

    expect(previewRows(text, ";")).toEqual({
      rows: [
        ["Fecha", "Detalle", "Importe"],
        ["15/10/2026", 'TRANSF; de "Ana"', "-1.500,00"],
        ["16/10/2026", "dos\nlíneas", "2"],
      ],
      columns: 3,
    });
  });

  it("corta en las filas pedidas y cuenta la más ancha", () => {
    const text = "a,b\nc,d,e\nf\ng\n";

    expect(previewRows(text, ",", 2)).toEqual({
      rows: [
        ["a", "b"],
        ["c", "d", "e"],
      ],
      columns: 3,
    });
  });

  it("una última fila sin salto de línea también cuenta", () => {
    expect(previewRows("a\tb", "\t").rows).toEqual([["a", "b"]]);
  });

  it("un archivo vacío no tiene columnas", () => {
    expect(previewRows("", ";")).toEqual({ rows: [], columns: 0 });
  });
});

describe("decode", () => {
  it("lee Windows-1252 con sus tildes", () => {
    const bytes = new Uint8Array([0x50, 0x61, 0x6e, 0xed]).buffer;

    expect(decode(bytes, "windows-1252")).toBe("Paní");
  });

  it("dice que no cuando los bytes no son esa codificación", () => {
    const bytes = new Uint8Array([0x50, 0xed, 0x41]).buffer;

    expect(decode(bytes, "utf-8")).toBeNull();
  });

  it("un archivo binario no es texto", () => {
    expect(decode(new Uint8Array([0x50, 0x4b, 0x00, 0x04]).buffer, "utf-8")).toBeNull();
  });
});
