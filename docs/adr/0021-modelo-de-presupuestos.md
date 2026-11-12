# ADR-0021: Modelo de presupuestos: topes mensuales con vigencia, en su propia moneda

* **Estado:** Aceptado
* **Fecha:** 2026-11-12

## Contexto

La fase 5 pide presupuestos mensuales por categoría, y después alertas al 80 % y al 100 %. Hay que decidir, antes de crear la tabla, cosas difíciles de revertir:

1. **Cómo se repite un tope** de un mes a otro, y qué pasa con los meses anteriores cuando cambia.
2. **En qué moneda está el tope**, si la persona gasta en pesos y en dólares y puede cambiar su moneda de referencia (ADR-0017).
3. **Qué pasa con lo que sobra** de un mes.
4. **Qué pasa con los topes de una categoría que se borra.**
5. **Dónde vive el módulo**, y cómo lee gasto, categorías y cotizaciones de otros módulos.

Las cuatro primeras son decisiones de producto, y la persona dueña del proyecto las tomó el 2026-11-12, entre dos o tres opciones cada una. Este ADR registra las alternativas y lo que implican.

Hechos verificados:

* Una categoría solo se puede borrar si no tiene movimientos (ADR-0011, `DeleteCategory`). Hoy ninguna pantalla borra categorías: solo la API.
* La clave foránea de los movimientos ya apunta a `(id, owner_id, kind)` de la categoría. Así la base garantiza que sea de la misma persona y del tipo correcto.
* El dashboard ya lee a otros módulos por su capa de aplicación, con adaptadores (ADR-0018), y convierte cada monto con la cotización de su día, del lado prudente (ADR-0017).

## Opciones consideradas

### Repetición del tope

#### Opción A: vigencias solo de agregado ("desde este mes, el tope es tal")
* Pros:
  * Se carga una vez y vale todos los meses.
  * Cambiarlo no reescribe la historia: octubre sigue mostrando el tope que tenía en octubre.
  * La tabla es su propio registro de auditoría: nunca se actualiza ni se borra una fila.
* Contras:
  * Leer un mes pide buscar la última vigencia que empezó hasta ese mes, y no una fila directa.
  * Hace falta un desempate para dos cambios en el mismo mes.

#### Opción B: un monto por mes
* Pros: lectura directa, y control total de cada mes.
* Contras:
  * Hay que cargar o copiar cada mes.
  * Un mes que nadie cargó queda sin presupuesto, en silencio.

#### Opción C: un solo tope por categoría, que se pisa al cambiar
* Pros: es lo más simple.
* Contras: los meses pasados mostrarían un tope que no tenían, y eso es un dato falso.

### Moneda del tope

#### Opción A: cada tope en su moneda, pesos o dólares
* Pros:
  * Cambiar la moneda de referencia no toca ningún tope.
  * Quien piensa su alquiler en dólares lo presupuesta en dólares.
* Contras:
  * Medir un mes puede pedir dos conversiones distintas, a pesos y a dólares.

#### Opción B: siempre la moneda de referencia
* Pros: una sola moneda en toda la pantalla.
* Contras:
  * Si la referencia pasa de pesos a dólares, un tope de 300.000 pasaría a valer 300.000 dólares.
  * Habría que convertir o borrar los topes al cambiar una preferencia.

### Lo que sobra de un mes

#### Opción A: no se acumula
* Pros:
  * Cada mes se mide desde cero, con una regla fácil de explicar y de auditar.
  * Acumular se puede agregar después sin migrar nada: es una regla de lectura sobre las mismas vigencias.
* Contras: no sirve para gastos irregulares, como un seguro anual.

#### Opción B: pasa al mes siguiente
* Pros: sirve para gastos irregulares.
* Contras: suma reglas, por ejemplo qué pasa al pasarse, al cambiar el tope o al quitarlo.

### Categoría borrada

#### Opción A: el borrado se lleva sus topes (`ON DELETE CASCADE`)
* Pros:
  * Movimientos no necesita saber que existen presupuestos, así que la dependencia queda en un solo sentido.
  * Como la categoría solo se borra sin movimientos, su gasto era cero en todos los meses: no se pierde ningún gasto.
* Contras:
  * Se pierde la historia de topes de esa categoría.

#### Opción B: bloquear el borrado si tiene topes
* Pros: no se pierde nada.
* Contras:
  * Movimientos tendría que consultar a presupuestos, y la dependencia quedaría al revés: el módulo base dependería del que lo usa.
  * O habría que dejar que la base rechace el borrado y traducir ese error, un acoplamiento escondido.

## Decisión

* **Repetición:** opción A, vigencias solo de agregado.
  * Crear, cambiar o quitar un tope agrega una fila desde el mes en curso de Argentina. Quitarlo es una fila sin monto.
  * El mes de un tope que ya pasó no se puede cambiar.
  * Las vigencias de una categoría están en orden estricto por momento de registro. Una restricción única de la base lo exige, y el caso de uso nunca registra dos en el mismo instante.
  * Pedir el mismo tope que ya vale no agrega nada. Por eso fijar es un `PUT` idempotente y no necesita `Idempotency-Key`.
* **Moneda:** opción A, pesos o dólares; por defecto, la de referencia.
  * Bitcoin no, porque no tiene cotización (ADR-0017).
  * Un gasto en otra moneda se convierte con la cotización de su día y el dólar elegido en las preferencias, como algo que se debe.
  * Lo que no se puede convertir, por ejemplo Bitcoin o un día sin cotización, no entra en lo gastado: se informa aparte, en su moneda.
* **Sobrante:** opción A, no se acumula.
* **Categoría borrada:** opción A, cascada. Si los topes de una categoría desaparecen mientras se lee un mes, la pantalla los omite.
* **Módulo:** `budgets` tiene sus propias tablas.
  * Lee categorías, gastos, el tipo de dólar y cotizaciones por la capa de aplicación de cada módulo, con adaptadores, como el dashboard.
  * Ningún otro módulo lo importa.
  * Las dos reglas están en los contratos de import-linter.
* **Medición:**
  * Lo gastado se redondea una vez, al final (`ROUND_HALF_EVEN`). Lo que queda es la resta de los dos números que se muestran.
  * El estado pasa a advertencia desde el 80 % y a pasado desde el 100 %. Esos umbrales viven en el dominio, para que las alertas de la fase 5 usen los mismos.
* **Interfaz:**
  * El mes vive en la URL (ADR-0020).
  * Quitar un tope no pide confirmación, porque se puede deshacer: avisa y ofrece "Deshacer", que vuelve a fijar el mismo tope (docs/design-system.md, patrones de interacción).

## Consecuencias

* Positivas:
  * La historia de topes es verificable fila por fila, sin un registro de auditoría aparte.
  * Cambiar preferencias no rompe ningún presupuesto.
  * Movimientos, cuentas, cotizaciones y preferencias no saben que existen presupuestos.
* Negativas / costos aceptados:
  * Leer un mes trae todas las vigencias hasta ese mes y elige en memoria. Una persona tiene decenas de categorías, así que son cientos de filas en el peor caso. Si creciera, se resuelve con `DISTINCT ON` en la consulta, sin cambiar la tabla.
  * Medir un mes pide, en el peor caso, dos series de cotizaciones, una hacia pesos y otra hacia dólares. Solo se piden si algún gasto está en otra moneda convertible.
  * Borrar una categoría se lleva su historia de topes. Cuando exista una pantalla que borre categorías, tiene que avisarlo antes.
  * "Deshacer" deja dos filas más en la historia: la que quita el tope y la que lo vuelve a poner. Es lo que pasó, y así queda registrado.
* Riesgos y cómo se mitigan:
  * **Una categoría se borra entre la validación y la escritura del tope.** La clave foránea lo rechaza, y el repositorio lo traduce a `BUDGET_CATEGORY_NOT_FOUND` en lugar de un error 500. Un test de integración lo prueba.
  * **El reloj del navegador está corrido en el cambio de mes.** El mes en curso no viaja en la URL ni en el pedido: el servidor lo decide con la zona de Buenos Aires.

## Supuestos y datos faltantes

* Se supone que nadie necesita topes que empiecen en un mes futuro. Si aparece la necesidad, la tabla ya lo admite: solo cambia el caso de uso.
* Se supone que el gasto que cuenta es el de todas las cuentas. Si se pidiera un tope por cuenta, sería otra columna y otra clave única.

## Referencias

* [ADR-0011](0011-modelo-de-movimientos.md): categorías y su borrado.
* [ADR-0017](0017-conversion-al-consultar.md): conversión al consultar, del lado prudente.
* [ADR-0018](0018-modelo-de-lectura-del-dashboard.md): lectura de otros módulos por su capa de aplicación.
* [ADR-0020](0020-pantalla-del-dashboard.md): filtros en la URL.
* WCAG 2.2: 1.4.1 (uso del color), 1.4.11 (contraste de lo que no es texto).
