import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // En desarrollo, /api va al backend local: mismo origen que en producción, sin CORS.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    restoreMocks: true,
    unstubGlobals: true,
    // material-color-utilities importa sus módulos sin extensión .js: Node no los
    // resuelve, así que Vite los procesa igual que en el build.
    server: { deps: { inline: ["@material/material-color-utilities"] } },
    // Vitest devuelve vacío todo CSS que no figure acá; tokens.test.ts necesita leer los tokens.
    css: { include: [/shared\/design\/tokens\.css/] },
    // Dos entornos: la app corre en el navegador (jsdom) y el Worker en el servidor (node).
    projects: [
      {
        extends: true,
        test: {
          name: "app",
          include: ["src/**/*.test.{ts,tsx}"],
          environment: "jsdom",
          setupFiles: ["./src/test/setup.ts"],
        },
      },
      {
        extends: true,
        test: {
          name: "worker",
          include: ["worker/**/*.test.ts"],
          environment: "node",
        },
      },
    ],
  },
});
