import { afterEach, describe, expect, it, vi } from "vitest";

import { saveFile } from "./saveFile";

describe("saveFile", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("descarga el contenido con el nombre pedido y libera el enlace", () => {
    const content = new Blob(["{}"], { type: "application/json" });
    const create = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:rinde/archivo");
    const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const clicked: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push(this);
    });

    saveFile("rinde-datos.json", content);

    expect(create).toHaveBeenCalledWith(content);
    expect(clicked).toHaveLength(1);
    expect(clicked[0]?.download).toBe("rinde-datos.json");
    expect(clicked[0]?.href).toBe("blob:rinde/archivo");
    expect(revoke).toHaveBeenCalledWith("blob:rinde/archivo");
  });
});
