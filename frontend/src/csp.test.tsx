import { render } from "@testing-library/react";
import { Button } from "react-aria-components";
import { afterEach, describe, expect, it, vi } from "vitest";

import nginxTemplate from "../nginx/default.conf.template?raw";
import cloudflareHeaders from "../public/_headers?raw";

// ADR-0010: React Aria inyecta un único <style> y la CSP lo permite por su
// hash, no con 'unsafe-inline'. Si una actualización cambia ese texto, este
// test falla antes de que la violación llegue a producción.

const STYLE_ID = "react-aria-pressable-style";

async function sha256Base64(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return btoa(String.fromCharCode(...new Uint8Array(digest)));
}

function styleSrcOf(policySource: string): string {
  const match = /style-src ([^;"]+)/.exec(policySource);
  if (!match?.[1]) {
    throw new Error("La política no tiene style-src");
  }
  return match[1];
}

describe("CSP", () => {
  afterEach(() => {
    document.getElementById(STYLE_ID)?.remove();
  });

  it("permite por hash el estilo que inyecta React Aria, y nada más en línea", async () => {
    // React Aria no inyecta el estilo cuando NODE_ENV es "test": se simula producción.
    vi.stubEnv("NODE_ENV", "production");
    render(<Button>Probar</Button>);
    vi.unstubAllEnvs();

    const style = document.getElementById(STYLE_ID);
    expect(style, "React Aria dejó de inyectar su estilo: revisar ADR-0010").not.toBeNull();
    const hash = `'sha256-${await sha256Base64(style?.textContent ?? "")}'`;

    for (const [name, source] of [
      ["public/_headers", cloudflareHeaders],
      ["nginx/default.conf.template", nginxTemplate],
    ] as const) {
      expect(styleSrcOf(source), name).toBe(`'self' ${hash}`);
    }
  });
});
