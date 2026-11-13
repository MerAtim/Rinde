# ADR-0024: Reglas de categoría al importar: texto contenido, gana la más específica

* **Estado:** Aceptado
* **Fecha:** 2026-11-12

## Contexto

Al importar un archivo (ADR-0023), cada línea arranca en la categoría "Otros" de su tipo, y la persona la cambia una por una. Los mismos comercios se repiten todos los meses, así que la fase 6 pide reglas: "si la descripción dice COTO, es Supermercado".

Hay que decidir cómo se crea una regla, cómo coincide con una línea y qué pasa si coinciden dos. Las dos primeras preguntas de producto las respondió la persona dueña del proyecto el 2026-11-12:

* Las reglas se crean desde la vista previa, no en una pantalla aparte.
* Si dos reglas coinciden, gana la más específica.

## Opciones consideradas

### Cómo coincide una regla

#### Opción A: la descripción contiene el texto, plegado
Se comparan las dos formas sin tildes, en minúsculas y con un solo espacio entre palabras, igual que la búsqueda de movimientos (ADR-0011).
* Pros:
  * Es fácil de explicar: "si dice COTO".
  * Las descripciones de los bancos traen números de sucursal o de operación que cambian; "contiene" los ignora.
* Contras:
  * Un texto corto puede coincidir de más: "PAN" también está en "PANAMERICANA". Se pide un mínimo de tres caracteres, y la vista previa dice qué regla eligió cada categoría.

#### Opción B: expresiones regulares
* Pros: máxima precisión.
* Contras: nadie las escribe sin errores, y una expresión mal hecha puede colgar el servidor (ReDoS).

### Cuál gana entre dos

#### Opción A: la más específica, el texto más largo
* Pros: es predecible y no hay nada que ordenar: "COTO DIGITAL" le gana a "COTO".
* Contras: dos textos distintos del mismo largo pueden coincidir; se desempata por orden alfabético, que es estable pero arbitrario.

#### Opción B: un orden elegido a mano
* Pros: control total.
* Contras: pide una pantalla para ordenar, que la persona decidió no tener.

## Decisión

* **Coincidencia:** opción A, texto contenido y plegado, de 3 a 60 caracteres.
* **Conflictos:** opción A, gana el texto más largo; a igual largo, el primero en orden alfabético.
* **Tipo:** una regla es de gastos o de ingresos, según la categoría. Solo se aplica a líneas de su tipo, así una regla de gastos nunca propone una categoría a un ingreso.
* **Creación:** al confirmar un lote, cada línea puede llevar el texto a recordar. Se guarda en la misma transacción que marca el lote como confirmado.
* **Reemplazo:** guardar el mismo texto otra vez, en el mismo tipo, reemplaza la categoría. Una restricción única por persona, tipo y texto lo garantiza.
* **Propuesta:** la vista previa propone las dos primeras palabras de la descripción, que la persona puede cambiar. Recordar un texto cambia también, en la pantalla, las otras líneas del mismo lote que lo contienen.
* **Dónde vive:** en el módulo de importación, que es el único que las usa. Una categoría borrada se lleva sus reglas (`ON DELETE CASCADE`), como sus topes y sus alertas (ADR-0021, ADR-0022).

## Consecuencias

* Positivas:
  * La segunda importación de un banco llega casi toda categorizada.
  * Cada categoría propuesta dice de dónde salió: una regla o el "Otros" de su tipo.
* Negativas / costos aceptados:
  * No hay una pantalla para ver o borrar reglas. Una regla equivocada se corrige recordando el mismo texto con otra categoría. Si hace falta más, se agrega una pantalla sin cambiar el modelo.
  * La coincidencia se escribe dos veces: en el servidor, que es la que vale, y en la pantalla, para mostrar al momento el efecto de una regla nueva. Un test de cada lado prueba los mismos casos.
* Riesgos y cómo se mitigan:
  * **Un texto demasiado general.** El mínimo de tres caracteres y la vista previa, que muestra qué regla eligió cada categoría antes de confirmar.
  * **Una regla de otra persona.** Las reglas se leen y se escriben siempre con el dueño, y la clave foránea pide una categoría de la misma persona.

## Supuestos y datos faltantes

* Se supone que las descripciones de un mismo comercio comparten un texto estable. El PDF de Macro, el próximo formato, lo confirma en la muestra disponible.

## Referencias

* [ADR-0011](0011-modelo-de-movimientos.md): búsqueda de movimientos sin tildes ni mayúsculas.
* [ADR-0023](0023-modelo-de-importacion.md): lotes, vista previa y confirmación.
* OWASP, "Regular expression Denial of Service (ReDoS)": por qué no se aceptan expresiones regulares.
