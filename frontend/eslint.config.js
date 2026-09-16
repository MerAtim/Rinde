import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import { defineConfig, globalIgnores } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";

export default defineConfig([
  globalIgnores(["dist", "coverage", "src/shared/api/schema.d.ts"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    rules: {
      // Candado contra XSS: React escapa por defecto, y estas son las únicas
      // puertas por las que entra HTML sin escapar. Si alguna vez hace falta,
      // se desactiva en esa línea con un comentario que explique por qué.
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message:
            "dangerouslySetInnerHTML inyecta HTML sin escapar. Renderizar el texto como hijo.",
        },
        {
          selector: "AssignmentExpression > MemberExpression[property.name=/^(inner|outer)HTML$/]",
          message: "Asignar innerHTML u outerHTML inyecta HTML sin escapar. Usar textContent.",
        },
        {
          selector: "CallExpression[callee.property.name='insertAdjacentHTML']",
          message: "insertAdjacentHTML inyecta HTML sin escapar. Construir nodos.",
        },
        {
          selector: "CallExpression[callee.property.name='write'][callee.object.name='document']",
          message: "document.write inyecta HTML sin escapar.",
        },
      ],
    },
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ["src/test/**", "**/*.test.{ts,tsx}"],
    rules: { "react-refresh/only-export-components": "off" },
  },
]);
