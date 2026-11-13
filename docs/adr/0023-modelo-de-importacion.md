# ADR-0023: Importación de movimientos: lote guardado, vista previa y huella por línea

* **Estado:** Aceptado
* **Fecha:** 2026-11-12

## Contexto

La fase 6 pide importar movimientos desde archivos del banco, con vista previa, deduplicación y reglas de categorización. Hay que decidir, antes de crear tablas:

1. **Qué formatos** se aceptan primero.
2. **Cómo es el flujo** entre subir el archivo y guardar los movimientos.
3. **Cómo se reconoce un duplicado**, contra lo importado antes y contra lo cargado a mano.
4. **Cómo se trata el archivo**, que es entrada no confiable.

Las decisiones de producto las tomó la persona dueña del proyecto el 2026-11-12, entre dos o tres opciones cada una:

* Se importan movimientos de cuenta (caja de ahorro o cuenta corriente). Los resúmenes de tarjeta quedan para después, porque las cuotas llegan en la fase 7.
* Un duplicado se marca en la vista previa y queda afuera, pero se puede incluir igual.
* Las categorías se eligen en la vista previa, y se puede guardar una regla que las próximas importaciones aplican solas.
* Primero un CSV genérico, con columnas que elige la persona; después el resumen PDF de Banco Macro.

Hechos verificados el 2026-11-12, con los bancos que usa la persona:

* Banco Macro, desde la app, entrega el resumen mensual en PDF. Trae fecha `dd/mm/aa`, descripción, referencia, débitos y créditos en columnas separadas y sin signo, con montos en formato argentino (`1.234,56`). Trae además saldo inicial, totales de débitos y créditos y saldo final, que cierran exacto.
* Cuenta DNI, de Banco Provincia, muestra los movimientos sin forma de descargarlos y con fechas sin año.
* De BBVA y del home banking de Provincia no hay muestras: la persona no tiene acceso hoy. No se construye un importador para un formato que no se vio.

## Opciones consideradas

### Flujo

#### Opción A: lote guardado en el servidor
Subir el archivo crea un lote con sus líneas ya leídas. La vista previa muestra el lote, y confirmar dice qué líneas entran y con qué categoría.
* Pros:
  * Lo que se guarda es lo que el servidor leyó: la confirmación no puede cambiar montos ni fechas.
  * Cada movimiento queda atado a su origen: lote, huella del archivo y número de línea. Es la trazabilidad que pide un auditor.
  * Confirmar dos veces el mismo lote no duplica nada: el lote cambia de estado una sola vez.
* Contras:
  * Dos tablas más, y lotes abandonados que hay que limpiar.

#### Opción B: vista previa sin estado
El servidor lee el archivo y devuelve las líneas; la confirmación manda las líneas de vuelta.
* Pros: no guarda nada hasta confirmar.
* Contras:
  * El cliente puede mandar otra cosa que lo leído, y se pierde el vínculo con el archivo.
  * Repetir la confirmación pide otra clave de idempotencia.

### Duplicados

#### Opción A: huella por línea, y parecido por cuenta, fecha y monto
* Cada línea importada guarda una huella: SHA-256 de cuenta, fecha, monto con signo, descripción normalizada y el número de vez que esa misma combinación aparece en el archivo. Así dos cafés iguales del mismo día son dos líneas, y reimportar el mismo archivo da las mismas huellas.
* Contra lo cargado a mano, que no tiene huella, se marca "posible duplicado" si hay un movimiento en la misma cuenta, con la misma fecha y el mismo monto.
* Pros:
  * El duplicado exacto lo garantiza la base, con una restricción única.
  * El parecido lo decide la persona: queda afuera por defecto, pero se puede incluir.
* Contras:
  * Si el banco cambia la descripción de un movimiento entre dos descargas, la huella cambia. El parecido por fecha y monto lo atrapa igual.

#### Opción B: solo fecha y monto
* Pros: simple.
* Contras: dos gastos iguales del mismo día serían siempre duplicados.

### Formatos

#### Opción A: una estrategia por formato
Cada formato es un lector que recibe bytes y devuelve líneas normalizadas: fecha, descripción, monto con signo y referencia. El CSV genérico recibe además cómo leerlo: separador, codificación, formato de número y qué columna es cada cosa.
* Pros:
  * Sumar un banco no toca el flujo: es un lector más (patrón Strategy).
  * Cada lector se prueba solo, con archivos inventados de la misma forma que los reales.
* Contras: el CSV genérico pide que la persona elija las columnas la primera vez.

#### Opción B: detectar el banco y el formato solo
* Pros: menos pasos.
* Contras: adivinar columnas en un archivo de plata es arriesgado, y equivocarse en el signo da vuelta un gasto.

## Decisión

* **Flujo:** opción A, lote guardado.
  * Un lote vence a las 24 horas si no se confirma, y la limpieza lo borra.
  * Confirmar registra los movimientos con un caso de uso de movimientos, por su capa de aplicación, en una sola transacción de base: entran todos o ninguno. Cada uno deja su registro de auditoría. El evento de gasto (ADR-0022) se publica una vez por mes del lote y no por línea: las alertas miden el mes entero, así que un evento alcanza, y un archivo de cientos de gastos no dispara cientos de mediciones.
* **Duplicados:** opción A, huella y parecido.
  * La huella se guarda en el movimiento, con una restricción única por cuenta. Lotes y movimientos son de módulos distintos, cada uno con su transacción: si el lote no llega a marcarse como confirmado después de guardar los movimientos, confirmarlo otra vez saltea lo que ya entró. La garantía contra duplicados vive en un solo lugar y no depende de que las dos escrituras salgan juntas.
* **Formatos:** opción A, una estrategia por formato. Primero el CSV genérico, después el PDF de Macro.
  * Del CSV: separador coma, punto y coma o tabulación; codificación UTF-8 o Windows-1252, que es la de Excel en español; números con coma decimal o con punto decimal; fecha `dd/mm/aaaa` o `aaaa-mm-dd`. El monto puede venir en una columna con signo o en dos columnas, débito y crédito.
  * Del PDF de Macro: se lee la capa de texto, nunca una imagen. La suma de las líneas tiene que cerrar con los totales del resumen; si no cierra, el lote se rechaza entero.
* **Signo y tipo:** un monto negativo es gasto y uno positivo es ingreso. Una transferencia entre cuentas propias no se puede reconocer desde un solo archivo: la persona la excluye en la vista previa.
* **Archivo como entrada no confiable:**
  * Hasta 1 MB y 2.000 líneas. Un PDF, hasta 20 páginas.
  * Una línea que no se puede leer no se adivina: se informa con su número y el motivo, y no entra.
  * El archivo no se guarda: se guardan su huella SHA-256, su nombre y las líneas leídas.
  * Una descripción de más de 120 caracteres se corta, como en un movimiento cargado a mano.

## Consecuencias

* Positivas:
  * Todo movimiento importado se puede rastrear hasta su archivo y su línea.
  * Reimportar el mismo archivo no duplica nada, y la base lo garantiza.
  * Sumar BBVA o Provincia es escribir un lector, cuando haya una muestra.
* Negativas / costos aceptados:
  * Dos tablas nuevas, lotes y líneas, y una tarea de limpieza de lotes vencidos.
  * La primera vez, la persona tiene que decir qué columna es cada cosa.
  * Las transferencias propias se excluyen a mano.
  * Leer PDF suma una dependencia (`pdfplumber`). Se fija la versión, y se lee con límites de tamaño y de páginas.
* Riesgos y cómo se mitigan:
  * **Un archivo armado para colgar el servidor.** Límites de tamaño, líneas y páginas antes de leer, y la lectura del CSV no evalúa nada: las fórmulas son texto.
  * **Una lectura que pierde o duplica líneas.** En el PDF, los totales de control. En el CSV, la vista previa muestra la suma de lo que entra antes de confirmar.
  * **Un lote de otra persona.** Todo lote y toda línea filtran por el dueño, y un test lo verifica para cada endpoint.

## Supuestos y datos faltantes

* Se supone que el resumen PDF de Macro mantiene sus columnas. Si cambia, los totales de control lo detectan y el lote se rechaza.
* Falta un PDF real de Macro para escribir su lector; la captura disponible alcanza para el diseño, no para la implementación.
* Faltan muestras de BBVA y del home banking de Provincia.

## Referencias

* [ADR-0011](0011-modelo-de-movimientos.md): movimientos, auditoría e idempotencia.
* [ADR-0022](0022-alertas-de-presupuesto.md): el evento de un gasto, que la importación también publica.
* RFC 4180: formato CSV.
* OWASP, "File Upload Cheat Sheet".
