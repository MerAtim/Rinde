# ADR-0026: Compras en cuotas

* **Estado:** Aceptado
* **Fecha:** 2026-11-14

## Contexto

En Argentina se compra en cuotas todo el tiempo: una heladera en 12 cuotas se paga de a una por mes, en cada resumen de la tarjeta. La fase 7 pide registrarlas con un reparto exacto.

Se decidió con la persona usuaria que **cada cuota cuenta en su mes**: los presupuestos y el dashboard ven lo que se paga cada mes, no el total el día de la compra.

Hechos del sistema actual:

* Un movimiento no puede tener fecha futura (ADR-0011): saldos, presupuestos, alertas, importación y dashboard asumen que todo lo guardado ya pasó.
* El hosting no tiene tareas programadas (ADR-0005).
* La regla del proyecto para repartos es asignación por resto mayor: la suma de las partes cierra exacta con el total.

## Opciones consideradas

### Opción A: crear las N cuotas como movimientos al comprar, con fecha futura
* Pros: una sola escritura, sin nada que generar después. Los presupuestos de los meses que vienen ya ven sus cuotas.
* Contras:
  * Rompe la regla de ADR-0011. Habría que filtrar "hasta hoy" en los saldos, la lista, la importación (posibles duplicados) y cualquier lectura futura: un olvido muestra plata que todavía no se pagó.
  * El saldo de hoy de la cuenta incluiría deuda que todavía no se facturó, o habría que excluirla en cada consulta.

### Opción B: un plan de cuotas, y cada cuota se vuelve movimiento cuando llega su fecha
* Pros:
  * Ningún movimiento con fecha futura: todo lo que ya lee movimientos sigue igual.
  * Las cuotas pendientes salen del plan, calculadas, sin filas que filtrar.
  * El mismo mecanismo sirve para los movimientos recurrentes, que vienen después.
* Contras:
  * Hay que generar las cuotas que vencieron. Sin tareas programadas, eso pasa cuando alguien usa la app.
  * El presupuesto de un mes futuro no ve sus cuotas hasta que llega ese mes.

## Decisión

Opción B. Es la única que no obliga a cambiar cada lectura de movimientos, y una lectura olvidada en la opción A mostraría montos que no pasaron.

**1. El plan.** Un gasto en una cuenta y una categoría, con el total a pagar, la cantidad de cuotas (de 2 a 48) y la fecha de la compra. Se guarda en `installment_plans`, con las mismas claves foráneas que un movimiento: la cuenta y la categoría son de la misma persona, la moneda es la de la cuenta y la categoría es de gastos.

**2. El reparto.**
* Cuota base = total ÷ cantidad, truncada al centavo. Los centavos que sobran se asignan de a uno por resto mayor. Con partes iguales todos los restos empatan, y el desempate es el orden: las primeras cuotas llevan un centavo más.
* La suma de las cuotas es siempre el total. Una prueba generativa lo verifica.
* El total es lo que se paga, con interés o sin él. Rinde no calcula intereses.

**3. Las fechas.** La cuota 1 es el día de la compra y cada una de las siguientes, el mismo día del mes siguiente. Un 31 en un mes de 30 días cae el último día del mes. Es una simplificación: la tarjeta factura según su fecha de cierre, que Rinde no conoce.

**4. Cuándo una cuota se vuelve movimiento.** Cuando su fecha llegó, en el día de Argentina.
* Al crear el plan, en la misma transacción: una compra de hace tres meses entra con sus cuatro primeras cuotas.
* Al abrir la app: la pantalla pide `POST /api/installments/due`, que genera lo vencido de todos los planes de la persona.
* Cada cuota generada es un movimiento común, con su registro en la auditoría y la marca de su plan y su número. `UNIQUE (installment_plan_id, installment_number)` en la base garantiza que dos pedidos a la vez no la dupliquen.
* Una cuota borrada no se vuelve a generar: la fila sigue ahí, marcada como borrada, y la restricción lo impide.

**5. Cancelar.** Un plan se cancela (por ejemplo, porque se adelantaron las cuotas o se devolvió la compra): las cuotas ya generadas quedan, porque pasaron, y no se generan más.

**6. Lo pendiente.** `GET /api/installments` devuelve cada plan con su calendario. Cada cuota dice si ya es un movimiento y, si lo es, cuál. El total pendiente lo calcula el servidor.

## Consecuencias

* Positivas:
  * Saldos, presupuestos, alertas, importación y dashboard no cambian: siguen leyendo solo lo que pasó.
  * Cada cuota se puede editar o borrar como cualquier movimiento, con su auditoría.
  * El reparto cierra exacto, y la base impide cuotas duplicadas.
* Negativas / costos aceptados:
  * Si nadie abre la app, las cuotas vencidas no se generan. Un cliente que usa la API directamente tiene que pedir `POST /api/installments/due`. Lo que se pierde es puntualidad, no datos: se generan después con su fecha correcta.
  * El presupuesto de un mes futuro no muestra sus cuotas hasta que llega el mes. La pantalla de cuotas sí las muestra.
  * Una cuota generada en el mes en curso dispara las alertas una vez por mes, como la importación (ADR-0022). Una de un mes pasado no, porque las alertas solo miran el mes en curso.
  * Editar una cuota no cambia el plan: el pendiente se calcula con el calendario original.
* Riesgos y cómo se mitigan:
  * **Dos pestañas abren la app a la vez.** La restricción única hace que la segunda inserción falle sin duplicar; la generación inserta con `ON CONFLICT DO NOTHING` y cuenta solo lo que entró.
  * **Fecha de cierre real de la tarjeta.** Si hace falta, se agrega al plan en un ADR nuevo, sin cambiar el reparto.

## Supuestos y datos faltantes

* Se supone que 48 cuotas alcanzan: los planes habituales llegan a 24, y algunos créditos de comercios, a 36.
* No se mide cuánto tarda la generación con muchos planes. Hoy se recorren solo los planes activos de una persona.

## Referencias

* [ADR-0005](0005-hosting-gratuito.md): hosting sin tareas programadas.
* [ADR-0011](0011-modelo-de-movimientos.md): modelo de movimientos y auditoría.
* [ADR-0022](0022-alertas-de-presupuesto.md): alertas por evento.
