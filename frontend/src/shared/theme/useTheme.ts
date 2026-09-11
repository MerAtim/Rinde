import { useCallback, useState } from "react";

export type Theme = "dark" | "light";

const STORAGE_KEY = "rinde.theme";

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

/**
 * Tema de la interfaz. /theme-init.js lo aplica antes del primer pintado;
 * este hook lo lee y lo cambia. Oscuro por defecto (ADR-0006).
 */
export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(currentTheme);

  const setTheme = useCallback((next: Theme) => {
    const root = document.documentElement;
    root.dataset.theme = next;

    // La barra del navegador en el celular acompaña al fondo del tema.
    const background = getComputedStyle(root).getPropertyValue("--md-sys-color-background").trim();
    if (background) {
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", background);
    }

    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Almacenamiento no disponible (modo privado): el tema dura la sesión.
    }
    setThemeState(next);
  }, []);

  return [theme, setTheme];
}
