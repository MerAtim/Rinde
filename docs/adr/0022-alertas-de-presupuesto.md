# ADR-0022: Alertas de presupuesto: eventos en el proceso, evaluación por estado

* **Estado:** Aceptado
* **Fecha:** 2026-11-12

## Contexto

La fase 5 cierra con alertas in-app cuando un presupuesto llega al 80 % y al 100 % de su tope (ADR-0021), disparadas por eventos de dominio al registrar gastos. Hay que decidir:

1. **Cuántas veces avisa** un mismo umbral, **dónde** se ve y **qué meses** cuentan.
2. **Cómo se entera** el módulo de alertas de que hubo un gasto, sin que movimientos dependa de él.
3. **Qué garantía de entrega** tiene una alerta si algo falla entre el gasto y el aviso.

Las tres decisiones del punto 1 son de producto. La persona dueña del proyecto las tomó el 2026-11-12, entre dos o tres opciones cada una.

Hechos verificados:

* La API corre como un único servicio web en Render, sin un proceso aparte para tareas en segundo plano (`.github/workflows/cd.yml`).
* Cada adaptador entre módulos abre su propia unidad de trabajo (ADR-0018), así que medir un presupuesto no puede ocurrir dentro de la transacción del gasto.
* `GetBudgets` ya mide el mes completo de una persona, con los umbrales del dominio de presupuestos (ADR-0021).
* Todavía no hay correo saliente: no hay dominio propio (decisión de autenticación de la fase 2).

## Opciones consideradas

### Producto

* **Repetición:** una vez por mes y por umbral (elegida), o cada vez que se cruza. Repetir obliga a definir qué es "bajar" del umbral: borrar un gasto, subir el tope o que cambie la cotización. Eso es más ruido y más reglas.
* **Dónde:** una campana con la cantidad sin leer y una lista, más un aviso breve en el momento (elegida). Las otras opciones eran solo el aviso, que se pierde si no se lee, o solo la campana.
* **Meses:** solo el mes en curso (elegida), o cualquier mes. Una alerta sirve para frenar a tiempo, y un mes cerrado ya no se corrige. La pantalla de presupuestos igual muestra cómo cerró cada mes.

### Cómo se entera alertas de un gasto

#### Opción A: movimientos publica un evento, y alertas se suscribe
* Pros:
  * Movimientos no sabe que existen las alertas: solo publica un hecho en un puerto (`EventPublisher`).
  * La suscripción se arma en la raíz de composición, el único lugar que conoce a todos los módulos.
  * Agregar otro interesado, por ejemplo una regla de categorización, no toca movimientos.
* Contras:
  * Hay un mecanismo más, el bus de eventos, que hay que probar y documentar.

#### Opción B: movimientos llama a alertas
* Pros: es directo y fácil de seguir.
* Contras: invierte la dependencia. El módulo base dependería del que lo usa, como se descartó en ADR-0021 para el borrado de categorías.

#### Opción C: alertas consulta los gastos cada cierto tiempo
* Pros: movimientos no cambia.
* Contras: pide un proceso periódico que hoy no existe, y el aviso llega tarde.

### Garantía de entrega

#### Opción A: publicar en el proceso, después de confirmar el gasto, y evaluar por estado
* Pros:
  * No pide infraestructura nueva.
  * El gasto queda confirmado antes de evaluar nada. Si la evaluación falla, por ejemplo porque no hay cotización, se registra en el log y el pedido responde bien igual. Devolver un error haría que el cliente reintente y duplique el gasto.
  * La evaluación no mira cuánto cambió el gasto, sino el estado del mes entero, y la base no admite dos alertas iguales. Por eso evaluar dos veces da lo mismo que evaluar una, y una alerta perdida la levanta el próximo gasto del mes.
  * La respuesta del gasto llega cuando la alerta ya está guardada, así que la interfaz la ve apenas vuelve a pedir las alertas.
* Contras:
  * Si el proceso se cae entre la confirmación y la evaluación, la alerta se demora hasta el próximo gasto de ese mes, o no llega si no hay otro.

#### Opción B: bandeja de salida transaccional (outbox)
* Pros: el evento se guarda en la misma transacción que el gasto, y ninguno se pierde.
* Contras:
  * Pide un proceso que lea la bandeja y la vacíe, con reintentos y limpieza, y Render no lo tiene en este plan.
  * Suma una tabla y una carrera más, entre la respuesta y el procesamiento.

#### Opción C: evaluar dentro de la transacción del gasto
* Pros: la alerta y el gasto se confirman juntos.
* Contras:
  * La medición lee a otros módulos con sus propias unidades, así que no comparte la transacción.
  * Una falla al medir, por ejemplo una cotización caída, haría fallar el registro del gasto.

## Decisión

* **Producto:**
  * Una alerta por categoría, mes y umbral.
  * Si un gasto pasa directo del 79 % al 120 %, avisa solo el 100 %, porque el aviso más fuerte incluye al otro.
  * Solo cuenta el mes en curso de Argentina.
  * Las alertas se ven en una campana con la cantidad sin leer y en una lista; además hay un aviso breve en el momento.
* **Eventos:** opción A.
  * Movimientos publica `ExpenseRecorded` al registrar, editar o restaurar un gasto, después de confirmar.
  * Es el contrato público del módulo, así que vive en su capa de aplicación (`transactions.application.events`) y no en el dominio: alertas no puede ver el dominio de otro módulo.
  * Borrar un gasto no publica nada, porque el gasto solo baja. Cambiar un tope tampoco, porque quien lo cambia está viendo el resultado; el próximo gasto evalúa igual.
* **Bus:** un bus en memoria, en el kernel compartido (`shared.infrastructure.events`). Llama a cada suscriptor en orden. Si un suscriptor falla, lo registra en el log y sigue con los demás, sin cortar el pedido.
* **Entrega:** opción A.
  * La evaluación mide el mes en curso con el caso de uso de presupuestos, a través de su capa de aplicación.
  * Una restricción única de la base, `(owner_id, category_id, month, threshold)`, hace que evaluar sea idempotente, aunque dos pedidos lleguen a la vez.
* **Contenido:** cada alerta guarda una foto de lo que había al dispararse: el tope y lo gastado, en la moneda del tope. Si después cambia el tope, la alerta sigue diciendo lo que pasó.
* **Lectura:**
  * `GET /api/alerts` devuelve las últimas 50 y la cantidad sin leer.
  * `POST /api/alerts/read` marca como leídas las que se le pasan, que son las que la persona vio en la lista. Marcar "todas" del lado del servidor podría marcar una que llegó mientras tanto.
* **Categoría borrada:** como en ADR-0021, se lleva sus alertas (`ON DELETE CASCADE`).

## Consecuencias

* Positivas:
  * Movimientos, presupuestos, cotizaciones y preferencias no saben que existen las alertas.
  * Una alerta perdida se recupera sola con el próximo gasto, sin procesos aparte.
  * La regla de "una vez" la garantiza la base, no un `if`.
* Negativas / costos aceptados:
  * Registrar un gasto tarda un poco más: espera a que se mida el mes. Son pocas consultas por persona, y se acepta a cambio de que la alerta ya esté cuando la interfaz la pide.
  * Si el proceso se cae justo después de confirmar un gasto y no hay otro gasto en el mes, esa alerta no llega. La pantalla de presupuestos sigue mostrando el estado real.
  * Si dos gastos llegan a la vez, uno puede guardar la alerta del 80 % y el otro la del 100 %. Son dos avisos verdaderos, y la restricción única evita los repetidos.
  * Marcar una alerta como leída cambia su fila. No es dinero ni historia de movimientos, así que no lleva registro de auditoría: alcanza con la fecha de lectura.
* Riesgos y cómo se mitigan:
  * **Un suscriptor que falla en silencio.** Cada falla queda en el log con el tipo de evento y el suscriptor, y un test prueba que no corta el pedido ni a los demás suscriptores.
  * **Un evento con datos de otra persona.** La evaluación usa el dueño que viene en el evento, el mismo del gasto, y todas las consultas filtran por él.

## Supuestos y datos faltantes

* Se supone que medir un mes es barato: decenas de categorías y cientos de gastos por persona. Si creciera, la evaluación podría limitarse a la categoría del evento.
* Si algún día hay un proceso en segundo plano, la bandeja de salida (opción B) se puede agregar detrás del mismo puerto `EventPublisher`, sin tocar los casos de uso.
* Si se pide avisar por correo, hace falta un dominio propio y un ADR nuevo.

## Referencias

* [ADR-0018](0018-modelo-de-lectura-del-dashboard.md): lectura de otros módulos por su capa de aplicación.
* [ADR-0021](0021-modelo-de-presupuestos.md): presupuestos, umbrales y cascada al borrar una categoría.
* Chris Richardson, *Microservices Patterns*, patrón "Transactional outbox": la alternativa descartada.
* Vaughn Vernon, *Implementing Domain-Driven Design*, capítulo 8: eventos de dominio y su publicación después de confirmar.
