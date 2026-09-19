# ADR-0013: Pruebas de extremo a extremo

* **Estado:** Aceptado
* **Fecha:** 2026-09-18

## Contexto

El proyecto tiene 244 tests de backend y 185 de frontend, y ninguno corre en un navegador. Los de componente usan jsdom, que no tiene motor de maquetado: no calcula posiciones ni tamaños. Todo lo que dependa de cómo queda una pantalla es invisible para la suite.

El historial lo muestra: de los últimos diez commits de corrección, varios son de maquetado (una barra superior recortada en celulares, un código de recuperación cortado en dos, tipografías que no cargaban), y los encontró siempre una persona mirando la pantalla, nunca la CI.

El roadmap ubicaba las pruebas de extremo a extremo en la fase 8, junto al portfolio.

## Decisiones

### 1. Se empiezan ahora y no en la fase 8

Adelantar una fase necesita justificación y esta es concreta: es el único tipo de prueba que puede ver la clase de error que más se repite. Dejarlo para el final significa convivir hasta entonces con un punto ciego conocido, y el costo de arrancar es bajo porque Playwright ya estaba en el stack.

* **Costo aceptado:** una dependencia más en el frontend (`@playwright/test` y `@types/node`) y alrededor de un minuto más de CI, entre bajar el navegador y correr las pruebas.

### 2. Corren contra el build de producción, con la API simulada

Las pruebas levantan el build servido por `vite preview` e interceptan las llamadas a la API con respuestas fijas.

* **Por qué el build y no el servidor de desarrollo:** es el mismo CSS y el mismo paquete que se despliega. Un problema de maquetado que solo aparece con los estilos minificados no se ve de otra forma.
* **Por qué la API simulada:** lo que se mide es cómo queda la pantalla, y para eso los datos tienen que ser siempre los mismos. Un backend real agrega una fuente de inestabilidad que no aporta nada a esta pregunta.
* **Alternativa descartada:** correr contra la dirección pública. Sería la prueba más realista y la más inestable: depende de la red, de que el servicio gratuito no esté dormido, y escribiría datos en producción.

### 3. Los flujos críticos completos quedan para después

Registrarse, abrir una cuenta y registrar un movimiento contra el entorno completo de `docker compose` es lo que pide la fase 8. Va en su propio pull request: necesita otra infraestructura y no tiene sentido mezclarlo con esto.

### 4. Se verifica una invariante, no un texto

La primera prueba no dice "Movimientos entra en el rail", que se rompería con cualquier palabra nueva o cualquier idioma agregado. Dice que nada de lo que hay dentro de una opción de la navegación puede salirse de su caja, en seis anchos de ventana y en los dos idiomas, porque el ancho depende de la palabra y alcanza con que una no entre.

### 5. Un reintento, y solo en CI

* **Por qué uno:** distingue un fallo de infraestructura de uno real sin tapar una prueba genuinamente inestable, que queda marcada como tal.
* **Por qué solo en CI:** en la máquina de quien desarrolla, un fallo tiene que fallar a la primera.

## Consecuencias

* Positivas: el punto ciego de maquetado deja de serlo. Una regresión de este tipo ahora falla en la CI en lugar de aparecer en una captura de pantalla semanas después.
* Negativas / costos aceptados: una dependencia más, un minuto más de CI, y el navegador hay que bajarlo una vez por clon. El hook `pre-push` lo exige y explica cómo, con `RINDE_SKIP_E2E=1` como salida explícita (ADR-0012, decisión 4).
* Riesgos: que las pruebas se vuelvan inestables y se empiecen a ignorar. Mitigación: sin esperas fijas, solo aserciones que reintentan solas, y datos simulados en vez de un backend.

## Nota sobre la primera prueba

Se escribió creyendo que había un error: que la etiqueta "Movimientos" se salía del rail y quedaba cortada, a partir de una captura de pantalla. La prueba se corrió primero contra el código sin tocar, esperando que fallara, y pasó. La medición mostró que el rail ocupa de 0 a 88 px y la etiqueta de 3 a 85: entra, con poco margen, y eso es lo que se lee como pegado al borde.

Queda registrado porque es el argumento más fuerte a favor de tener estas pruebas: convierten "se ve mal" en una medición, y esta vez sirvieron para descartar un error que no existía en lugar de confirmar uno que sí.

## Referencias

* [ADR-0006: Sistema de diseño propio sobre Material 3](0006-sistema-de-diseno.md)
* [ADR-0012: Chequeos locales y su relación con la CI](0012-chequeos-locales-y-en-ci.md)
* https://playwright.dev/docs/best-practices
