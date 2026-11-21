# ADR-0034: Borrar la cuenta en el momento y exportar los datos en un JSON

* **Estado:** Aceptado
* **Fecha:** 2026-11-21

## Contexto

Rinde guarda las finanzas de cada persona. La Ley 25.326 de Protección de los Datos Personales da a cada titular derecho a acceder a sus datos (art. 14) y a pedir que se supriman (art. 16). La supresión tiene que hacerse en un plazo de cinco días hábiles desde que se pide. OWASP ASVS (V8, protección de datos) pide además que una persona pueda borrar y exportar sus datos por sí misma.

Hasta ahora no había forma de hacer ninguna de las dos cosas desde la app.

Hechos del sistema que condicionan la decisión:

* Todas las tablas con datos de una persona apuntan a `users` con `ON DELETE CASCADE`, auditoría incluida (ADR-0028, migración 0018). Borrar el usuario se lleva todo.
* Una demo no tiene contraseña que su dueño conozca, y se borra sola a las dos horas (ADR-0028).
* Hay respaldos diarios cifrados que se guardan 90 días (ADR-0033). Lo borrado sigue en ellos hasta que vencen.

## Opciones consideradas

### Cómo se borra

#### Opción A: en el momento, confirmado con la contraseña

* Pros:
  * Es lo más simple: un solo `DELETE` dentro de una transacción.
  * Cumple de sobra el plazo de la ley.
  * Pedir la contraseña sigue a OWASP ASVS para operaciones sensibles: una sesión que quedó abierta en otro equipo no alcanza para borrar la cuenta.
* Contras:
  * Un error no tiene vuelta atrás desde la app.

#### Opción B: desactivar la cuenta 30 días y borrarla después

* Pros:
  * Deja arrepentirse.
  * Protege de quien use una sesión ajena, aunque esa persona igual necesitaría la contraseña.
* Contras:
  * Suma un estado más a la cuenta, que cada consulta tiene que tener en cuenta.
  * Necesita un proceso programado, y el plan gratuito de Render no tiene programador de tareas.
  * Durante 30 días los datos siguen vivos aunque la persona pidió borrarlos.

### En qué formato se exportan

#### Opción 1: un único JSON

* Pros:
  * Completo y estructurado.
  * Lo puede leer otro programa, que es lo que pide la portabilidad.
  * Un solo archivo y un solo formato para mantener.
* Contras:
  * No se abre cómodo en una planilla.

#### Opción 2: un JSON más un CSV de movimientos, en un ZIP

* Pros:
  * Los movimientos se abren directo en Excel.
* Contras:
  * Dos formatos que mantener en sincronía.
  * Más código y más pruebas.

## Decisión

La persona que opera el sistema eligió A y 1 el 2026-11-21.

**Borrado:** `POST /api/auth/me/delete`, con la contraseña en el cuerpo. Es POST y no DELETE porque la RFC 9110 no le define significado al cuerpo de un DELETE, y un intermediario lo puede descartar.

* La contraseña cuenta para los mismos topes de intentos que el inicio de sesión, por cuenta y por origen.
* Una demo responde `DEMO_NOT_DELETABLE`: no tiene contraseña con la que confirmar, y se borra sola.
* En la misma transacción se borran el usuario, sus sesiones y sus intentos fallidos, que guardan el nombre de usuario, y se escribe una constancia de la baja.
* El frontend vacía la caché, para que no quede nada de la cuenta en memoria, y lleva a la pantalla de ingreso con un aviso.

**Constancia de bajas:** la tabla `account_deletions` guarda solo el identificador de la cuenta y la fecha, sin ningún dato de la persona y sin clave foránea. Sirve para un caso concreto. Si se restaura un respaldo anterior a una baja, la cuenta borrada vuelve a aparecer, y esta lista dice cuáles hay que borrar de nuevo. Es lo que recomiendan las guías de protección de datos para los respaldos: no se editan, pero la baja se vuelve a aplicar al restaurar. El paso está en [docs/respaldos.md](../respaldos.md).

**Exportación:** un JSON con todo lo de la persona, ordenado por sección y con nombres claros. Nunca incluye los hashes de la contraseña ni del código de recuperación. Se arma pidiéndole sus datos a cada módulo por su capa de aplicación, como hace el dashboard (ADR-0018). Una prueba falla si aparece una tabla con datos de una persona que la exportación no cubre. Llega en un PR propio, después del borrado.

## Consecuencias

* Positivas:
  * Cada persona puede borrar su cuenta y llevarse sus datos sin pedirle nada a nadie.
  * Una prueba de integración verifica, a partir de las claves foráneas y no de una lista escrita a mano, que después de borrar no queda ninguna fila de esa cuenta en ninguna tabla que apunte a `users`, y que otra cuenta queda intacta. Una tabla nueva entra sola en la prueba.
* Negativas / costos aceptados:
  * Un borrado por error no se puede deshacer desde la app.
  * Los datos borrados siguen hasta 90 días dentro de los respaldos cifrados, que solo puede abrir quien tiene la clave privada. Editar cada respaldo para sacar una cuenta rompería la prueba de restauración que los valida, y sacarla al restaurar logra lo mismo.
  * `account_deletions` crece con cada baja, sin datos personales: un identificador y una fecha por fila.
* Riesgos y cómo se mitigan:
  * **Restaurar un respaldo y olvidarse de volver a aplicar las bajas:** el paso está en la guía de restauración, antes de cambiar la base en uso.
  * **Adivinar la contraseña desde una sesión robada:** cada intento cuenta para el bloqueo por cuenta y por origen, igual que en el inicio de sesión.

## Supuestos y datos faltantes

* **Logs:** se asume que ningún log guarda datos de las personas. Hoy la API no los escribe. Si se suma un registro de eventos de seguridad, tiene que definir su propia retención y entrar en este análisis.
* **Copias fuera de Rinde:** una persona puede tener copias propias, como exportaciones o capturas. Quedan fuera del alcance.

## Referencias

* [Ley 25.326 de Protección de los Datos Personales](https://www.argentina.gob.ar/normativa/nacional/ley-25326-64790/texto), arts. 14 y 16
* [OWASP ASVS 4.0.3, V8: Data Protection](https://github.com/OWASP/ASVS/blob/v4.0.3/4.0/en/0x16-V8-Data-Protection.md)
* [RFC 9110, sección 9.3.5: DELETE](https://www.rfc-editor.org/rfc/rfc9110#section-9.3.5)
