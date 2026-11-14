# ADR-0027: Movimientos recurrentes

* **Estado:** Aceptado
* **Fecha:** 2026-11-14

## Contexto

El alquiler, el sueldo, la prepaga y las suscripciones se repiten igual todos los meses. La fase 7 pide registrarlos sin cargarlos a mano cada vez.

Se decidió con la persona usuaria que **se crean solos al llegar la fecha**, sin que haya que confirmarlos uno por uno.

Hechos del sistema actual:

* Un movimiento no puede tener fecha futura (ADR-0011).
* El hosting no tiene tareas programadas (ADR-0005).
* Las compras en cuotas ya resuelven un problema parecido (ADR-0026): un plan guardado, y cada cuota se vuelve movimiento cuando llega su fecha, al abrir la app.
* En Argentina el alquiler y la prepaga se ajustan seguido: el monto de una regla cambia varias veces por año.

## Opciones consideradas

### Opción A: crear los movimientos de los próximos meses por adelantado
* Pros: el presupuesto de un mes futuro ya los ve.
* Contras:
  * Rompe ADR-0011, con el mismo problema que la opción A de ADR-0026: cada lectura tendría que filtrar "hasta hoy".
  * Una regla sin fin no tiene un último movimiento: habría que elegir un horizonte arbitrario y extenderlo.
  * Cambiar el monto obligaría a reescribir los movimientos futuros ya creados.

### Opción B: proponer cada movimiento y que la persona lo confirme
* Pros: nada entra sin que la persona lo vea; sirve para montos que cambian todos los meses.
* Contras:
  * No es lo que se decidió: el valor está en no tener que hacer nada.
  * Hace falta un estado nuevo, "propuesto", que el resto del sistema tendría que ignorar.

### Opción C: una regla, y cada movimiento se genera cuando llega su fecha
* Pros:
  * Ningún movimiento con fecha futura, igual que las cuotas.
  * Reutiliza el mecanismo de ADR-0026: generación al abrir la app, índice único y `ON CONFLICT DO NOTHING`.
  * Cambiar el monto afecta solo a lo que todavía no se generó.
* Contras:
  * Si nadie abre la app, lo vencido espera.
  * Un monto que cambió y nadie actualizó entra con el monto viejo; la persona lo corrige como cualquier movimiento.

## Decisión

Opción C. Es la que se eligió, no cambia ninguna lectura de movimientos y usa un mecanismo que ya está probado en producción.

**1. La regla.** Un gasto o un ingreso en una cuenta y una categoría, con un monto fijo, una frecuencia (semanal, mensual o anual) y la fecha de la primera vez. Se guarda en `recurring_rules`, con las mismas claves foráneas que un movimiento: la cuenta y la categoría son de la misma persona, la moneda es la de la cuenta y la categoría es del tipo de la regla.

**2. Las fechas.** La vez `n` (desde 1) es la primera fecha más `n - 1` semanas, meses o años. Mensual y anual caen el mismo día; un 31 en un mes de 30 días cae el último día, y un 29 de febrero, el 28 en un año no bisiesto. Se calcula siempre desde la primera fecha, no desde la anterior, para que un 31 no se vuelva 30 para siempre después de abril.

**3. Primera fecha acotada.** Entre un año antes y un año después de hoy. Un error de tipeo (2016 en vez de 2026, semanal) generaría cientos de movimientos de golpe; un año atrás alcanza para ponerse al día con algo que se olvidó cargar, y una regla que empieza el mes que viene es válida.

**4. Cuándo se genera.** Igual que las cuotas (ADR-0026, decisión 4): al crear la regla, en la misma transacción, y al abrir la app con `POST /api/recurring/due`. Cada vez generada es un movimiento común, con su auditoría y la marca de su regla y su número. `UNIQUE (recurring_rule_id, recurrence_number)` impide duplicarla, y una borrada no se vuelve a generar.
* Para no recorrer toda la historia, se busca el número más alto ya generado (borrados incluidos) y se genera desde el siguiente.
* Si la cuenta está archivada, la regla no genera nada mientras siga así: archivar una cuenta es dejar de usarla.

**5. Cambiar el monto.** Se puede cambiar el monto y la descripción. Antes de guardar el cambio se genera lo que ya venció, con el monto anterior: el aumento del alquiler no reescribe los meses que ya pasaron. El resto (cuenta, tipo, categoría, frecuencia, primera fecha) no se cambia: se cancela la regla y se crea otra.

**6. Cancelar.** Lo ya generado queda, porque pasó; no se genera más. No hay "pausar": se cancela y, si vuelve, se crea otra.

**7. Un movimiento generado es de la persona.** Se edita y se borra como cualquier otro, tipo incluido: a diferencia de una cuota, no es parte de un total que tenga que cerrar.

## Consecuencias

* Positivas:
  * Saldos, presupuestos, alertas, importación y dashboard no cambian.
  * Una sola forma de "generar lo vencido" para cuotas y recurrentes, con las mismas garantías.
  * Los ajustes del alquiler se cargan una vez y valen desde la próxima.
* Negativas / costos aceptados:
  * Si nadie abre la app, lo vencido espera; se genera después con su fecha correcta.
  * El presupuesto de un mes futuro no ve lo recurrente hasta que llega el mes.
  * Sin montos variables: una factura de luz que cambia cada mes conviene cargarla a mano o importarla.
  * Sin transferencias recurrentes (por ejemplo, ahorrar todos los meses): una transferencia tiene dos cuentas y dos monedas, y es otro modelo. Si hace falta, se decide en otro ADR.
* Riesgos y cómo se mitigan:
  * **Una regla y la importación registran el mismo gasto.** La persona borra uno; el borrado de una vez generada no se regenera. Si es frecuente, la importación puede marcar coincidencias en el futuro.
  * **Dos pestañas a la vez.** El índice único y `ON CONFLICT DO NOTHING`, como en las cuotas.

## Supuestos y datos faltantes

* Se supone que semanal, mensual y anual cubren los casos comunes. "Cada dos meses" o "el último día hábil" quedan afuera hasta que alguien los pida.
* Se supone que un año hacia atrás alcanza para ponerse al día.

## Referencias

* [ADR-0005](0005-hosting-gratuito.md): hosting sin tareas programadas.
* [ADR-0011](0011-modelo-de-movimientos.md): modelo de movimientos y auditoría.
* [ADR-0026](0026-compras-en-cuotas.md): el mismo mecanismo de generación, para las cuotas.
