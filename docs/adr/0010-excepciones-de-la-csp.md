# ADR-0010: Excepciones puntuales de la CSP

* **Estado:** Aceptado
* **Fecha:** 2026-09-17

## Contexto

La CSP publica `style-src 'self'` y `font-src 'self'` (ADR-0006), y CI y CD rechazan cualquier `unsafe-inline`. Al probar las pantallas en un navegador real aparecieron dos violaciones en cada carga, ya presentes antes de la fase 2:

* **Estilo en línea.** `usePress` de React Aria agrega al cargar un `<style id="react-aria-pressable-style">` con `touch-action: pan-x pan-y pinch-zoom` para los elementos que se tocan. Sirve para que un toque en el celular no espere a descartar un doble toque de zoom (en Safari, `touch-action: manipulation` no alcanza). La CSP lo bloquea, así que hoy la optimización no se aplica y la consola informa un error en cada visita.
* **Fuente como `data:`.** Vite incrusta en el CSS como `data:` todo recurso de menos de 4 KiB. Uno de los subconjuntos de las tipografías autoalojadas entra en ese límite y `font-src 'self'` lo bloquea: los caracteres de ese subconjunto se ven con la fuente de respaldo.

ADR-0006 eligió React Aria en parte por ser compatible con la CSP. Ese supuesto era casi cierto, y hay que registrar la diferencia.

Hechos verificados:

* El texto que inyecta React Aria es fijo. Su SHA-256 es `38RhXrc7EdReTKsOm23ZPOCUgniTUUcjky8QOOrQx6o=`, el mismo que calcula Chrome en el reporte de la violación.
* React Aria acepta un nonce desde una etiqueta `<meta>` llamada `csp-nonce`, pero un nonce tiene que cambiar en cada respuesta, y el HTML se sirve como archivo estático (ADR-0005).
* CSP Level 3 admite hashes en `style-src` para elementos `<style>`.

## Opciones consideradas

### Opción A: permitir ese estilo por su hash

`style-src 'self' 'sha256-38RhXrc7EdReTKsOm23ZPOCUgniTUUcjky8QOOrQx6o='`.

* Pros: mecanismo estándar de la CSP; habilita solo ese texto exacto, no cualquier estilo en línea; no requiere servidor.
* Contras: si React Aria cambia una coma, el hash deja de coincidir y vuelve la violación sin aviso.

### Opción B: nonce por respuesta

Generar un nonce en el Worker o en nginx e inyectarlo en el HTML y en la cabecera.

* Pros: es el mecanismo que lee React Aria; sobrevive a cambios de su texto.
* Contras: el HTML deja de ser estático; nginx necesita un módulo extra para reescribir el cuerpo; un nonce mal generado o cacheado anula la protección de toda la política, no de un estilo.

### Opción C: tolerar la violación

Dejarla bloqueada y copiar la regla `touch-action` a `base.css`.

* Pros: la CSP no cambia.
* Contras: un error en consola en cada visita entrena a ignorar los errores de CSP, que son justo los que avisan de un XSS; si algún día se agrega `report-to`, cada visita genera un reporte falso.

### Para la fuente: dejar de incrustar tipografías

* Opción D: `font-src 'self' data:`. Contras: habilita cualquier fuente incrustada, incluida una inyectada.
* Opción E: que Vite no incruste fuentes y las sirva como archivo. Contras: una petición más por subconjunto usado, del orden de 4 KiB cada una.

## Decisión

Opción A para el estilo, con un test que genera el estilo real de React Aria, calcula su hash y exige que figure en las dos CSP; y opción E para las fuentes. Ninguna afloja la política más allá de lo que se usa.

## Consecuencias

* Positivas: la carga no produce violaciones; vuelve la optimización de toque en celulares; se mantiene la regla de CI sin `unsafe-inline`.
* Negativas / costos aceptados: una actualización de React Aria que cambie el texto rompe el test hasta actualizar el hash en `public/_headers` y en la plantilla de nginx; una petición extra por subconjunto tipográfico pequeño.
* Riesgos y cómo se mitigan: que el hash quede desactualizado sin que nadie lo note. Lo evita el test, que corre en cada PR de Dependabot.

## Supuestos y datos faltantes

* Se supone que el Worker de Cloudflare sigue sin reescribir el HTML. Si en algún momento lo hace, la opción B pasa a ser viable y conviene revisarla.

## Referencias

* https://www.w3.org/TR/CSP3/#grammardef-hash-source
* Código de React Aria: `react-aria/dist/private/interactions/usePress` y `utils/getNonce`
* https://vite.dev/config/build-options.html#build-assetsinlinelimit
* [ADR-0006: Sistema de diseño propio sobre Material 3](0006-sistema-de-diseno.md)
