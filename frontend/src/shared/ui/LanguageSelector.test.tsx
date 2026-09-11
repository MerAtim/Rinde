import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { LanguageSelector } from "./LanguageSelector";

describe("LanguageSelector", () => {
  it("empieza en español", () => {
    render(<LanguageSelector />);

    expect(screen.getByLabelText("Idioma")).toHaveValue("es");
  });

  it("cambia los textos y el idioma del documento al elegir inglés", async () => {
    const user = userEvent.setup();
    render(<LanguageSelector />);

    await user.selectOptions(screen.getByLabelText("Idioma"), "en");

    expect(screen.getByLabelText("Language")).toHaveValue("en");
    expect(document.documentElement.lang).toBe("en");
  });
});
