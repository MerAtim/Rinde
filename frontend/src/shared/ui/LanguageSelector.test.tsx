import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectNoA11yViolations } from "../../test/a11y";
import { LanguageSelector } from "./LanguageSelector";

describe("LanguageSelector", () => {
  it("empieza en español", () => {
    render(<LanguageSelector />);

    expect(screen.getByRole("radio", { name: "Español" })).toBeChecked();
  });

  it("cambia los textos y el idioma del documento al elegir inglés", async () => {
    const user = userEvent.setup();
    render(<LanguageSelector />);

    await user.click(screen.getByRole("radio", { name: "English" }));

    expect(screen.getByRole("radiogroup", { name: "Language" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
  });

  it("se puede operar con el teclado", async () => {
    const user = userEvent.setup();
    render(<LanguageSelector />);

    await user.tab();
    expect(screen.getByRole("radio", { name: "Español" })).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    await user.keyboard("{Enter}");

    expect(document.documentElement.lang).toBe("en");
  });

  it("no tiene problemas de accesibilidad", async () => {
    const { container } = render(<LanguageSelector />);

    await expectNoA11yViolations(container);
  });
});
