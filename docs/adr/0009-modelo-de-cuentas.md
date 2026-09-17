# ADR-0009: Modelo de cuentas

* **Estado:** Aceptado
* **Fecha:** 2026-09-17

## Contexto

La fase 2 empieza por las cuentas: efectivo, banco, tarjeta y billetera cripto, cada una con su moneda. Sobre ellas se apoyan los movimientos, las transferencias, los presupuestos y el patrimonio neto, así que las decisiones de este modelo son caras de revertir una vez que haya datos reales.

Restricciones vigentes:

* El dinero es `Money(amount, currency)` y no se mezclan monedas sin conversión (ADR-0002).
* Toda consulta filtra por el usuario autenticado, con un test que lo verifica para cada endpoint nuevo (CLAUDE.md).
* El objetivo de rendimiento de la fase 4: p95 menor a 300 ms en el dashboard con 50 000 movimientos.

## Decisiones

### 1. El saldo se calcula, no se guarda

El saldo de una cuenta es la suma de sus movimientos. El saldo inicial es un movimiento más.

* **Alternativa descartada:** una columna `balance` que se actualiza con cada movimiento. Es más rápida de leer, pero son dos fuentes de verdad para el mismo dato. Cualquier error, carrera o migración mal hecha las separa, y en una app de finanzas un saldo que no coincide con sus movimientos destruye la confianza en todo lo demás.
* **Costo aceptado:** leer un saldo cuesta una suma con índice por cuenta. Si la fase 4 mide que no alcanza, se agrega un saldo materializado como caché derivada y reconstruible, nunca como fuente de verdad.

### 2. La moneda de una cuenta no cambia

Se elige al crearla y queda fija. Cambiarla reinterpretaría todos los montos históricos: 1000 pesos pasarían a ser 1000 dólares. Si alguien se equivocó, archiva la cuenta y crea otra.

### 3. Las cuentas se archivan, no se borran

Borrar una cuenta dejaría huérfanos sus movimientos y rompería los reportes históricos y el log de auditoría. Archivar la saca de la vista diaria y la conserva para la historia. El borrado real llega con la exportación y el borrado de datos del usuario, como operación completa sobre toda su información.

### 4. Bitcoin solo en billeteras cripto

Una cuenta de efectivo, banco o tarjeta en BTC no existe en el mundo real, y admitirla abre errores de carga difíciles de detectar. Una billetera cripto admite cualquier moneda, porque las billeteras argentinas también guardan pesos y dólares.

### 5. Un recurso ajeno responde 404, no 403

Si la cuenta existe pero es de otra persona, la respuesta es la misma que si no existiera. Un 403 confirmaría que ese identificador existe, y eso ya es información (OWASP API Security Top 10, API1:2023, Broken Object Level Authorization).

Lo verifica un test reutilizable que recorre las rutas del esquema OpenAPI: una ruta nueva con un identificador en el camino falla si no tiene registrada la forma de crear un recurso ajeno para probarla. Así la regla no depende de acordarse.

### 6. El módulo se llama `accounts`

CLAUDE.md enumera los módulos en español (`cuentas`, `transacciones`) y también establece que el código y los identificadores van en inglés. Se sigue la segunda regla, que es la que ya respetan `auth` y `health`: el paquete es `rinde.accounts`, y el dominio se documenta en español.

## Consecuencias

* Positivas: el saldo no puede desincronizarse; los datos históricos no se reinterpretan ni se pierden; la autorización por dueño queda verificada automáticamente para cada endpoint nuevo.
* Negativas / costos aceptados: leer saldos cuesta una suma; una cuenta creada con la moneda equivocada no se corrige, se reemplaza.
* Riesgos: que la suma no alcance el objetivo de la fase 4. Mitigación: se mide con datos sembrados antes de optimizar, y la optimización prevista es una caché derivada.

## Referencias

* [ADR-0002: Representación de dinero y cotizaciones múltiples](0002-representacion-de-dinero-y-cotizaciones.md)
* https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/
