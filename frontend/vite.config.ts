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
