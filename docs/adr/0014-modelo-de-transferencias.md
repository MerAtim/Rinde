# ADR-0014: Modelo de transferencias

* **Estado:** Aceptado
* **Fecha:** 2026-09-19

## Contexto

Mover plata entre dos cuentas propias no es ni un gasto ni un ingreso: el patrimonio no cambia, cambia de lugar. Hoy no se puede registrar, y la única forma de reflejarlo es cargar un gasto en una cuenta y un ingreso en la otra. Eso deja los saldos bien y los reportes mal: aparece gasto que nunca existió y el resumen por categoría queda inservible.

Es la última pieza de la fase 2 y se apoya en dos modelos ya decididos, caros de revertir: las cuentas (ADR-0009) y los movimientos (ADR-0011).

Restricciones vigentes:

* El dinero es `Money(amount, currency)` y no se mezclan monedas sin una conversión registrada (ADR-0002).
* Todo movimiento tiene categoría obligatoria y su tipo coincide con el de la categoría (ADR-0011, decisión 3).
* El saldo se calcula, no se guarda (ADR-0009, decisión 1).
* El borrado es lógico y toda lectura tiene que excluir los borrados (ADR-0011, decisión 5).
* Las cotizaciones son la fase 3: hoy no hay de dónde sacar una tasa.

## Decisiones

### 1. La transferencia es una entidad propia, no dos movimientos enlazados

Una tabla `transfers` con cuenta de origen, cuenta de destino, el monto de cada lado y su fecha. `transactions` queda intacta.

* **Alternativa descartada:** dos filas en `transactions` con tipos `transfer_out` y `transfer_in`, unidas por un identificador de transferencia. Era más barata: el saldo ya suma por tipo, y la lista, los filtros, la paginación, el borrado lógico y la auditoría seguían funcionando sin tocar nada. Se descartó porque obliga a que la categoría pase a ser opcional, y entonces "todo movimiento tiene categoría" deja de ser una invariante y pasa a ser una costumbre. Además, que una transferencia no cuente como gasto queda dependiendo de que cada consulta se acuerde de filtrar por tipo; un olvido no rompe nada visible, solo ensucia un reporte.
* **A favor de la elegida:** que una transferencia no sea ni gasto ni ingreso queda garantizado por la forma de los datos y no por la disciplina de quien escribe la próxima consulta. Un reporte de gastos que lea `transactions` es correcto por construcción.
* **Costos aceptados, que son reales y no menores:**
  * El saldo de una cuenta pasa a ser la suma de sus movimientos más lo que recibió menos lo que envió: dos tablas en lugar de una.
  * La lista de movimientos tiene que unir dos fuentes, y la paginación por cursor sobre una unión es más difícil que sobre una tabla. Se resuelve en la decisión 5.
  * El borrado lógico y el log de auditoría hay que repetirlos para esta entidad.

### 2. Cada lado guarda su monto y su moneda, atados a su cuenta por la base

La fila lleva `amount_out` con `currency_out` y `amount_in` con `currency_in`. Cada par apunta a su cuenta con una clave foránea compuesta contra `(id, owner_id, currency)` de la cuenta, igual que hacen los movimientos.

* **Por qué:** la base garantiza que el monto que sale está en la moneda de la cuenta que lo envía y el que entra en la de la que lo recibe. No hay forma de escribir una transferencia incoherente, ni siquiera desde `psql`.
* **Consecuencia:** entre cuentas de la misma moneda los dos montos existen igual. Podrían ser distintos, y eso es correcto: una transferencia con comisión saca 1000 y deposita 990.

### 3. Entre monedas distintas no se convierte: se guardan los dos montos

Una transferencia de pesos a dólares guarda cuántos pesos salieron y cuántos dólares entraron, tal como los carga la persona. No se aplica ninguna cotización.

* **Por qué:** la tasa real de esa operación es la que le dieron a la persona, no la de ninguna tabla. Guardar los dos montos la conserva exacta; la tasa implícita se deduce dividiendo, cuando haga falta.
* **Alternativa descartada:** pedir una cotización y calcular el otro lado. Las cotizaciones son la fase 3 y, aunque existieran, introducirían un número inventado donde hay uno real.

### 4. Borrado lógico y auditoría, igual que los movimientos

Borrar una transferencia le pone fecha de borrado y la fila queda; se puede deshacer. Cada cambio se registra en un log que solo admite inserciones.

* **Por qué:** es dinero y las mismas razones de ADR-0011 decisión 5 valen acá. Además permite deshacer sin reconstruir la fila, que es lo que prefiere el sistema de diseño frente a un diálogo de confirmación.

### 5. La lista une las dos tablas con el mismo cursor

El historial se arma con una unión de movimientos y transferencias, ordenada por `(occurred_on, id)` y paginada por ese mismo par, aplicando el predicado del cursor a las dos ramas antes de unirlas.

* **Por qué así:** si el cursor se aplicara después de unir, habría que traer de más para poder descartar, y el costo crecería con la página. Aplicándolo en cada rama, cada una usa su índice y la unión ordena como mucho el doble del tamaño de página.
* **Costo aceptado:** las dos tablas tienen que ordenarse por el mismo par y tener el índice que lo acompaña. Queda escrito acá porque un índice que falte no rompe nada visible: solo hace la consulta lenta cuando haya datos.

### 6. Una transferencia no tiene categoría

No se le pone ninguna, ni siquiera una sembrada.

* **Alternativa descartada:** una categoría "Transferencia". Volvería a meter las transferencias en el resumen por categoría, que es justo lo que este modelo evita.

## Consecuencias

* Positivas: los reportes de gasto e ingreso son correctos por construcción. La tasa real de un cambio de moneda queda guardada exacta, sin depender de la fase 3. El patrimonio neto no se altera al mover plata.
* Negativas / costos aceptados: el saldo y la lista leen dos tablas; el borrado lógico y la auditoría están repetidos; hay dos caminos de escritura de dinero en lugar de uno.
* Riesgos: que la consulta de la lista unida no rinda con volumen. Mitigación: los índices de la decisión 5 y la medición prevista de la fase 4, con datos sembrados, antes de optimizar nada.

## Referencias

* [ADR-0002: Representación de dinero y cotizaciones múltiples](0002-representacion-de-dinero-y-cotizaciones.md)
* [ADR-0009: Modelo de cuentas](0009-modelo-de-cuentas.md)
* [ADR-0011: Modelo de movimientos](0011-modelo-de-movimientos.md)
