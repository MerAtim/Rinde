# ADR-0020: Pantalla del dashboard: gráficos, tabla equivalente y filtros en la URL

* **Estado:** Acepta y reemplaza en parte a ADR-0003 (Zustand para los filtros)
* **Fecha:** 2026-11-11

## Contexto

El endpoint del dashboard ya existe (ADR-0018). Falta la pantalla, y con ella cuatro decisiones difíciles de revertir:

1. **Dónde vive.** El inicio mostraba un saludo, el lema de la app, el dólar del día y el estado del servicio.
2. **Dónde viven los filtros.** ADR-0003 eligió Zustand para el estado de UI, con la URL como fuente de verdad.
3. **Con qué se dibuja.** El stack declarado nombra Chart.js (README, sección Stack).
4. **Cómo se dibuja sin hacer aritmética de dinero en el frontend** (ADR-0002) y sin depender del color (WCAG 1.4.1).

Hechos verificados:
* Los filtros de Movimientos ya viven solo en la URL, con `useSearchParams`. Zustand nunca se instaló.
* El validador de paletas de la guía de visualización (`validate_palette.js`, distancia OKLab por 100) midió el verde de ingreso contra el coral de gasto:
  * En el tema oscuro (`#90DA4F` y `#FFB4AA`), la distancia para deuteranopía es 8,5. Pasa el mínimo de 8.
  * En el tema claro (`#386B00` y `#AE3026`), es 3,9. Una persona con deuteranopía no los distingue.
  * Los dos pasan el contraste de 3:1 contra la superficie.
* Chart.js 4.6 no inyecta hojas de estilo: no hay `insertRule` ni `<style>` en su bundle. Cambia el tamaño del canvas por CSSOM, que la CSP no bloquea.

## Opciones consideradas

### Filtros

#### Opción A: solo la URL, leída con `useSearchParams`
* Pros:
  * Una sola fuente de verdad: no hay nada que sincronizar.
  * Un enlace reproduce la vista, recargar la conserva y Atrás deshace un filtro.
  * Es lo que ya hace Movimientos, y no suma dependencias.
* Contras:
  * Cada lectura parsea la URL. Son dos parámetros: el costo es despreciable.
  * Cambiar un filtro re-renderiza la pantalla entera. Los gráficos se vuelven a dibujar igual, porque cambian los datos.

#### Opción B: URL más Zustand, como dice ADR-0003
* Pros: respeta la decisión anterior sin cambios.
* Contras:
  * Dos copias del mismo estado y un sincronizador entre ellas, que es una fuente conocida de errores (por ejemplo, el botón Atrás contra un store que no se enteró).
  * Una dependencia más, sin un problema concreto que resuelva hoy.

### Gráficos

#### Opción A: Chart.js con react-chartjs-2, con una tabla equivalente por gráfico
* Pros:
  * Es la biblioteca del stack declarado: documentada, mantenida y conocida.
  * Escalas, tooltips y redimensionado resueltos.
  * Se registran solo las piezas que se usan, y se descarga recién cuando hay un gráfico que dibujar.
* Contras:
  * El canvas no lee variables de CSS: los colores se leen de los tokens en tiempo de ejecución y se vuelven a leer al cambiar el tema.
  * El canvas no es accesible por teclado ni por lector de pantalla. Por eso hace falta la tabla equivalente.
  * Son 58 kB comprimidos más, aunque en un archivo aparte.

#### Opción B: SVG propio, sin biblioteca
* Pros:
  * Los tokens se aplican directo desde CSS.
  * Cada marca puede ser enfocable, sin peso extra.
* Contras:
  * Escalas, marcas de eje, tooltips y redimensionado escritos y mantenidos a mano.
  * Es la solución ingeniosa en lugar de la estándar.
  * Contradice el stack declarado.

## Decisión

* **Ubicación.** El dashboard es el inicio. El dólar del día queda debajo, como contexto. Es una decisión de producto, tomada antes de construir.
* **Filtros.** Opción A, solo la URL. Reemplaza la parte de ADR-0003 que elegía Zustand para los filtros. Lo demás de ADR-0003 sigue vigente: TanStack Query para el estado de servidor, y Context para el tema y el idioma.
  * La URL guarda cuántos meses mirar (`months`), no un mes fijo: un enlace a "los últimos seis meses" sigue diciendo eso el mes siguiente.
  * Los parámetros se validan como cualquier dato de afuera. Un período que no está en la lista vuelve al de siempre, y una cuenta que no es un UUID no llega al servidor.
* **Gráficos.** Opción A, con estas reglas:
  * **Patrimonio:** una línea. Un cierre sin cotización corta la línea; no se inventa el tramo.
  * **Ingresos y gastos:** columnas que suben y bajan desde el cero. La posición dice qué es cada barra, así que no depende del par de colores, que en el tema claro falla para deuteranopía. Además, la leyenda dice de qué lado está cada serie.
  * **Gastos por categoría:** barras horizontales de un solo tono, dibujadas en HTML dentro de una tabla. Cada fila tiene escritos el nombre y el monto, así que la misma pieza es el gráfico y su versión accesible.
  * Cada gráfico de canvas tiene una tabla equivalente a un clic. El canvas lleva `role="img"` y un nombre que dice dónde están los valores.
  * Una tabla más ancha que la pantalla se desplaza dentro de su tarjeta. El contenedor es enfocable y tiene nombre, para poder desplazarlo con el teclado (WCAG 2.1.1).
  * Sin animación (docs/design-system.md, principio 4).
* **Dinero.** Un monto se convierte a `number` solo para ubicar una marca (`charts/series.ts`). Todo valor que se lee (tooltip, tabla, monto de cada fila) se formatea desde el string del servidor. Las marcas del eje son números redondos que calcula el gráfico para ubicarse, no montos de nadie. El signo del neto se lee del string, sin restar nada.

## Consecuencias

* Positivas:
  * Una vista se comparte con un enlace y sobrevive a recargar.
  * Quien no ve colores, o usa lector de pantalla o teclado, accede a los mismos valores.
  * El ingreso no descarga Chart.js.
* Negativas / costos aceptados:
  * El README nombraba Zustand en el stack: se corrige.
  * El canvas es una caja negra para jsdom. Los tests de componente reemplazan `react-chartjs-2`, y lo dibujado se prueba en el navegador (ADR-0013): que los dos canvas tengan tamaño, que nada desborde a 360 px en los dos idiomas y que no haya violaciones de la CSP de producción.
  * El eje del flujo muestra en positivo lo que está abajo del cero. Lo aclara la leyenda.
* Riesgos y cómo se mitigan:
  * **Una actualización de Chart.js empieza a inyectar estilos y choca con la CSP.** La prueba de navegador carga la página con la CSP de `public/_headers` y falla ante cualquier violación.
  * **El reloj del navegador está corrido en el cambio de mes, y el período pedido no coincide con el del servidor.** El mes se calcula con la zona de Buenos Aires, como en el servidor. Si igual no coincide, el servidor responde `DASHBOARD_PERIOD_INVALID` y la pantalla lo explica.

## Supuestos y datos faltantes

* Se supone que quien comparte un enlace quiere un período relativo ("los últimos 12 meses"). Si aparece la necesidad de un período fijo, se agrega `from`/`to` a la URL sin romper los enlaces actuales.
* La distancia de color del tema claro se midió con un validador de la guía de visualización, no con la herramienta de `tokens.test.ts`. Si se agregara esa verificación al test, el par de ingreso y gasto del tema claro fallaría. Hoy no hace falta, porque ningún dato depende solo del color, pero conviene revisarlo si se rediseña la paleta.

## Referencias

* [ADR-0002](0002-representacion-de-dinero-y-cotizaciones.md): dinero como string en el frontend.
* [ADR-0003](0003-gestion-de-estado-frontend.md): gestión de estado en el frontend.
* [ADR-0006](0006-sistema-de-diseno.md) y [docs/design-system.md](../design-system.md): tokens y "Gráfico de magnitud".
* [ADR-0013](0013-pruebas-de-extremo-a-extremo.md): pruebas de extremo a extremo.
* [ADR-0018](0018-modelo-de-lectura-del-dashboard.md): el endpoint.
* WCAG 2.2: 1.4.1 (uso del color), 2.1.1 (teclado).
