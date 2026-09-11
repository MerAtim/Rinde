# ADR-0006: Sistema de diseño propio sobre Material 3

* **Estado:** Aceptado
* **Fecha:** 2026-09-11

## Contexto

El frontend tiene que seguir Material Design 3 (Material You) con identidad propia: modo oscuro por defecto, profundidad visual, movimiento con intención y ninguna apariencia de plantilla SaaS genérica. Restricciones técnicas vigentes:

* La CSP publica `script-src 'self'` y `style-src 'self'`: no se permiten scripts ni hojas de estilo en línea ni de terceros.
* La accesibilidad (WCAG AA) es un requisito del proyecto, no un extra.
* La aplicación maneja datos financieros: el color no puede ser el único portador de significado.

Hechos relevados (septiembre de 2026):

* `@material/web`, la biblioteca oficial de componentes web de Material, está en modo mantenimiento: no recibe mejoras.
* `@material/material-color-utilities` (Apache 2.0) es la implementación oficial de Google que genera los esquemas de Material You desde un color semilla.
* `react-aria-components` (Apache 2.0) ofrece componentes accesibles sin estilos propios.
* Google Sans Flex se publicó con licencia SIL OFL 1.1 en noviembre de 2025; Lexend también es OFL.

## Opciones consideradas

### Opción A: tokens propios de Material 3 + React Aria + CSS Modules
* Pros: identidad visual completa; accesibilidad de teclado, foco y lectores de pantalla resuelta por React Aria; CSS estático compatible con la CSP; sin costo de ejecución.
* Contras: más código propio que mantener; cada componente necesita sus tests de accesibilidad.

### Opción B: `@material/web`
* Pros: componentes oficiales de Material 3.
* Contras: modo mantenimiento; Web Components con estilo difícil de personalizar a fondo en React.

### Opción C: MUI (Material UI)
* Pros: ecosistema grande, muchos componentes listos.
* Contras: su estilo por defecto sigue Material 2; inyecta estilos en tiempo de ejecución (Emotion), incompatibles con `style-src 'self'` sin nonces; el resultado tiende a verse como cualquier otra app hecha con MUI.

### Opción D: Tailwind + shadcn/ui
* Pros: rápido para prototipar.
* Contras: no es Material 3; es exactamente la estética de plantilla que el producto quiere evitar.

## Decisión

Opción A, con estas reglas:

* **Tokens como variables CSS.** Donde Material 3 define un nombre, se usa ese (`--md-sys-color-*`, `--md-sys-motion-*`, `--md-sys-state-*`, `--md-ref-typeface-*`); lo propio de Rinde lleva el prefijo `--rinde-`.
* **Color derivado y verificado.** Los roles de marca salen del esquema Tonal Spot con semilla `#33D6C4`. Un test recalcula los roles con `material-color-utilities` y falla si `tokens.css` se aparta, y verifica los contrastes mínimos en ambos temas.
* **Superficies del brief**, sin negro puro: `#0F1115`, `#171A21`, `#20252D` y sus escalones intermedios.
* **Sin gradientes.** La profundidad sale de la elevación tonal, las sombras y un filo de luz de un píxel.
* **Oscuro por defecto** aunque el sistema operativo esté en claro; el tema claro existe y se elige explícitamente. Un script propio (`/theme-init.js`) lo aplica antes del primer pintado, sin destello.
* **Tipografías autoalojadas:** Lexend para títulos y cifras grandes, Google Sans Flex para la interfaz. Nada se descarga de Google Fonts: lo exige la CSP y evita revelar a terceros la IP de cada usuario.
* **Íconos Material Symbols como SVG sueltos**: solo se empaquetan los que se usan.
* **Tests de accesibilidad con `axe-core`** para cada componente.

La especificación completa está en [docs/design-system.md](../design-system.md).

## Consecuencias

* Positivas: identidad propia sin pelear contra una biblioteca; accesibilidad verificable en CI; la paleta no puede desviarse en silencio de Material You.
* Negativas / costos aceptados: los componentes se construyen de a uno, cuando una pantalla los necesita; el empaquetado incluye los archivos de fuentes de todos los alfabetos (el navegador descarga solo los que usa, por `unicode-range`).
* Riesgos: inconsistencia entre componentes hechos en momentos distintos. Mitigación: todo valor visual sale de un token, y el documento de diseño es la referencia obligatoria.

## Referencias

* https://m3.material.io
* https://github.com/material-foundation/material-color-utilities
* https://react-spectrum.adobe.com/react-aria/components.html
* https://github.com/material-components/material-web/discussions/5642
