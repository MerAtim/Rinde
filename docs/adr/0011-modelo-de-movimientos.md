# ADR-0011: Modelo de movimientos

* **Estado:** Aceptado
* **Fecha:** 2026-09-18

## Contexto

Sobre las cuentas (ADR-0009) se apoyan los movimientos: ingresos y gastos en este corte, transferencias en el siguiente. De acá salen los saldos, los presupuestos, las alertas y los reportes, así que el modelo es caro de revertir una vez que haya datos reales.

Restricciones vigentes:

* El dinero es `Money(amount, currency)`, nunca `float`, y no se mezclan monedas (ADR-0002).
* Toda consulta filtra por el usuario autenticado, verificado por un test que recorre el esquema OpenAPI (CLAUDE.md, ADR-0009).
* Los POST que crean dinero aceptan `Idempotency-Key` y los cambios quedan en un log de auditoría append-only (CLAUDE.md).
* El saldo se calcula, no se guarda (ADR-0009, decisión 1).
* Objetivo de la fase 4: p95 menor a 300 ms en el dashboard con 50 000 movimientos.

## Decisiones

### 1. El signo lo da el tipo, no el monto

Un movimiento guarda un monto siempre positivo y un tipo (`income` o `expense`). El saldo es la suma de los ingresos menos la de los gastos.

* **Alternativa descartada:** un monto con signo. Habilita dos formas de escribir lo mismo (un gasto de 100 o un ingreso de menos 100), y cualquier consulta que agrupe por tipo tiene que confiar en que el signo y el tipo no se contradigan.
* **Costo aceptado:** un gasto cargado como ingreso se corrige editando el tipo, no cambiando el signo.

### 2. La moneda la impone la cuenta

El movimiento no elige moneda: hereda la de su cuenta, y la base lo verifica contra la fila de la cuenta. Sin esto, un gasto en dólares dentro de una caja en pesos rompería el saldo sin ninguna conversión registrada.

### 3. La categoría es obligatoria

Todo movimiento tiene categoría.

* **Alternativa descartada:** categoría opcional con un grupo "Sin categoría" en los reportes. Permite anotar un gasto en dos toques y clasificar después.
* **Costo aceptado:** registrar es un paso más largo. Se mitiga con una categoría "Otros" entre las sembradas y preseleccionando en el formulario la última categoría usada en esa cuenta, pero el costo no desaparece: existe el riesgo de que la gente elija cualquier categoría con tal de avanzar, y eso ensucia los reportes de una forma más difícil de detectar que un "Sin categoría" explícito.

### 4. Las categorías se siembran y también se crean

Cada persona tiene sus propias categorías. La primera vez que se piden, si no tiene ninguna, se siembran las típicas con un identificador estable (`supermercado`, `alquiler`, `sueldo`, `otros`), que la interfaz traduce a es y en; las propias se muestran tal cual se escribieron. Son filas suyas: puede renombrarlas y borrarlas.

* **Alternativa descartada:** una lista fija del sistema, más simple pero incapaz de cubrir casos propios.
* **Alternativa descartada:** sembrarlas al registrarse. Obligaría a que el registro escriba en otro módulo, o a que los dos compartan la misma sesión de base de datos para que la siembra y el alta del usuario sean una sola transacción. Cualquiera de las dos ata `auth` a `transacciones`.
* **Costo aceptado:** quien nunca abra sus categorías no las tiene, y la siembra ocurre dentro del primer pedido que las lee, que por eso tarda un poco más. La repetición no duplica: la base tiene una única fila por dueño e identificador sembrado, y una segunda siembra simultánea no escribe nada.
* Una categoría con movimientos no se borra: responde `CATEGORY_IN_USE` (409). Borrarla dejaría movimientos sin clasificar, que es justo lo que la decisión 3 quiso evitar.

### 5. El borrado es lógico

Borrar un movimiento le pone fecha de borrado; la fila queda.

* **Alternativa descartada:** borrar la fila y conservar la historia en el log de auditoría. Ninguna consulta puede equivocarse, porque no hay nada que filtrar.
* **Costo aceptado y su riesgo:** toda lectura tiene que excluir los borrados, y un olvido infla un saldo o un reporte sin que nadie lo note. Se mitiga así, no se elimina:
  * Ningún caso de uso arma consultas: el repositorio es el único acceso y todas sus lecturas parten del mismo constructor, que ya excluye los borrados.
  * Índices parciales sobre los movimientos vivos, que son los que se consultan.
  * Un test de integración que, por cada lectura del repositorio, inserta un movimiento borrado y exige que no aparezca. Una lectura nueva que se olvide del filtro falla ahí.
* **A favor:** habilita deshacer sin reconstruir la fila, que es lo que el sistema de diseño prefiere frente a un diálogo de confirmación.

### 6. El saldo vive en el módulo de movimientos

`GET /api/transactions/balances` devuelve el saldo por cuenta. La pantalla de cuentas lo pide y lo junta con la lista de cuentas.

* **Alternativa descartada:** que `GET /api/accounts` devuelva el saldo. Sería más cómodo para el frontend, pero pondría a `cuentas` a depender de `transacciones`, al revés de como se apoyan hoy.
* **Costo aceptado:** la pantalla de cuentas hace dos pedidos.

### 7. Idempotencia por tabla propia

`POST /api/transactions` acepta `Idempotency-Key`. Se guarda la clave junto al usuario, la huella del pedido y el movimiento que creó; una repetición con la misma huella devuelve ese movimiento, y la misma clave con un cuerpo distinto responde 409.

* **Alternativa descartada:** deducir el duplicado por los datos del movimiento (misma cuenta, monto y fecha). Dos cafés iguales el mismo día son dos gastos reales, no un duplicado.
* **Costo aceptado:** una tabla más, que hay que limpiar. Se borran las claves de más de 24 horas en cada escritura, como ya se hace con los intentos de ingreso.

## Consecuencias

* Positivas: los saldos no pueden desincronizarse; ningún movimiento queda sin moneda ni sin categoría; un reintento por red caída no duplica dinero; toda edición queda registrada.
* Negativas / costos aceptados: registrar exige elegir categoría; las lecturas cargan con el filtro de borrados; la pantalla de cuentas hace dos pedidos.
* Riesgos: que el saldo calculado no alcance el objetivo de la fase 4. Mitigación: se mide con datos sembrados antes de optimizar, y la optimización prevista sigue siendo una caché derivada y reconstruible (ADR-0009).

## Referencias

* [ADR-0002: Representación de dinero y cotizaciones múltiples](0002-representacion-de-dinero-y-cotizaciones.md)
* [ADR-0009: Modelo de cuentas](0009-modelo-de-cuentas.md)
* https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header
