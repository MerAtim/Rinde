# ADR-0018: Modelo de lectura del dashboard e histórico de cotizaciones por serie

* **Estado:** Aceptado
* **Fecha:** 2026-11-11

## Contexto

La fase 4 pide un dashboard con el gasto por categoría, el flujo de cada mes y el patrimonio neto, todo en la moneda de referencia de cada persona. Cada monto se convierte con la cotización de su fecha (ADR-0017). Además fija un objetivo medible: p95 menor a 300 ms del endpoint con 50.000 movimientos.

Hechos verificados:

* Hasta ahora los días pasados se piden de a uno a ArgentinaDatos y se guardan (ADR-0016). Seis meses son unos 180 días por tipo de dólar: de a uno, la primera vista tardaría minutos y le haría cientos de pedidos a una fuente que no publica límites de uso.
* ArgentinaDatos publica la serie completa de cada dólar en un solo pedido (`/v1/cotizaciones/dolares/{casa}`). El 2026-11-11 la del MEP traía 2.936 días desde el 2018-10-29, unos 290 KB, con un valor por día de calendario: los fines de semana repiten el último día hábil.
* Las tablas de movimientos y transferencias ya tienen índices parciales por dueño y fecha (ADR-0011, ADR-0014).

Restricciones: la regla de dependencias entre módulos (ADR-0001), nada de valores inventados, redondeo solo en los bordes y ninguna cuenta de dinero en el frontend.

## Opciones consideradas

### Dónde vive el dashboard

#### Opción A: endpoints nuevos dentro de movimientos
* Pros: los datos ya están ahí, sin adaptadores.
* Contras:
  * Movimientos tendría que depender de cotizaciones y de preferencias, y hoy no conoce a ninguno de los dos.
  * Un módulo de escritura cargaría con un reporte que no es suyo.

#### Opción B: una vista SQL que una las tablas de varios módulos
* Pros: una sola consulta.
* Contras:
  * Rompe la frontera entre módulos: la vista conoce las tablas de todos.
  * La conversión con la regla prudente de ADR-0017 quedaría en SQL, duplicada y sin las pruebas del dominio.

#### Opción C: un módulo `dashboard` de solo lectura
* Pros:
  * Lee a los otros módulos por su capa de aplicación, como manda ADR-0001, y ninguno depende de él.
  * El cálculo es una función pura, probada sin base ni red.
* Contras:
  * Un pedido abre tres o cuatro sesiones de base, una por módulo.
  * Hay que mantener adaptadores y tipos espejo.

### Cómo se llena el histórico

#### Opción A: seguir pidiendo de a un día
* Pros: no cambia nada.
* Contras: inviable para un período de meses, por tiempo y por la carga sobre la fuente.

#### Opción B: una tarea programada que cargue la serie cada noche
* Pros: el pedido de una persona nunca espera a la fuente.
* Contras: el hosting gratuito (ADR-0005) no da un planificador. Habría que sumar infraestructura solo para esto.

#### Opción C: traer la serie completa cuando a un rango le faltan días
* Pros:
  * Un pedido por tipo de dólar en vez de cientos.
  * No suma infraestructura.
  * Se guarda solo lo que hacía falta, y una fila guardada no se pisa (ADR-0016).
* Contras: el primer pedido que necesita días nuevos espera a la fuente.

## Decisión

Módulo `dashboard` de solo lectura (opción C) e histórico por serie a demanda (opción C). Son las únicas que respetan las fronteras entre módulos y no suman infraestructura.

**1. Histórico por serie.**
* Si a un rango le falta algún día cerrado, se pide la serie completa de ese dólar.
* Se guardan los días del rango que faltaban, más seis días antes del rango para poder arrastrar un precio.
* Se ignora lo de hoy, que todavía se mueve.
* La serie queda en memoria 15 minutos. Así, un rango con días que la fuente no tiene, como los anteriores a 2018, no la pide de nuevo en cada pedido.
* Para la serie, el tope de tamaño de una respuesta sube de 256 KB a 2 MB y el tiempo máximo de 3 a 10 segundos. Cualquier otra respuesta sigue con los topes de antes.

**2. Un día sin cotización propia toma la del último día anterior, hasta seis días.**
* Es lo que hace la misma fuente con los fines de semana: sin operaciones, vale el último precio.
* La cotización arrastrada conserva su fecha, así que se sabe de qué día es.
* Pasado ese tope, el dato falta.

**3. La base suma y Python convierte pocas filas.** Lo que se pide por día es solo lo que hay que convertir:
* Los flujos en otra moneda llegan sumados por día, categoría y moneda, porque cada día tiene su cotización.
* Los flujos en la moneda de referencia no se convierten, así que llegan sumados por mes.
* Los cambios de saldo llegan por cuenta y por mes, porque el patrimonio se mira al cierre de cada mes. Todo lo anterior al período llega junto, como saldo de apertura.
* Las transferencias cambian saldos, pero no son flujos.

**4. Conversión y redondeo.**
* Un ingreso se convierte como algo que se tiene y un gasto como algo que se debe: nunca se valúa de más lo que entra ni de menos lo que sale (ADR-0017). El patrimonio usa el signo del saldo de cada cuenta.
* Las conversiones se suman sin redondear, y cada número que se muestra se redondea una vez, con `ROUND_HALF_EVEN`.
* El neto de un mes es la resta de los dos números ya redondeados, para que lo que se ve cierre exacto.

**5. Nada inventado.**
* Lo que no se puede convertir no entra en los totales y se informa aparte, en su moneda (`unconverted`). Por ahora es el Bitcoin, o un día sin cotización.
* Un cierre de mes en el que alguna cuenta no tiene cotización queda sin total.

**6. El período.**
* Son meses enteros: por defecto los últimos seis y como máximo 24, que es lo que acota el costo de un pedido.
* El mes en curso termina hoy.
* El día que cuenta es el de Argentina, igual que en cotizaciones.

**7. La medición.**
* Una prueba de integración corre en CI contra PostgreSQL. Siembra un escenario fijo, con semilla:
  * 50.000 movimientos y 2.000 transferencias en dos años.
  * Seis cuentas, dos en dólares.
* Mide 60 pedidos de punta a punta: aplicación completa, sesión real, base real y conversión.
* El histórico ya está cargado y el período son los seis meses cerrados anteriores, así que no interviene la red.
* La prueba falla si el p95 llega a 300 ms. También comprueba que hubo gastos, que se convirtió y que no hubo pedidos a la red, para que no apruebe midiendo otra cosa.
* Medición local del 2026-11-11 (Windows, PostgreSQL 18):
  * Primera versión: p95 de 212 ms.
  * Final: p95 de 155 ms y p50 de 82 ms.
  * La diferencia salió de los puntos 3 y de calcular una sola vez la escala de cada moneda.

## Consecuencias

* Positivas:
  * El cálculo del dashboard es Python puro, con pruebas de cada regla. El neto que cierra exacto se verifica con una prueba generativa.
  * Ningún módulo depende del dashboard, y los contratos de import-linter lo verifican.
  * El objetivo de rendimiento corre en cada PR. Una regresión se ve antes de integrar.
* Negativas / costos aceptados:
  * El primer pedido que necesita días nuevos espera a la fuente: entre uno y dos segundos. Si la fuente está caída, esos días figuran como sin cotización hasta que vuelva.
  * La medición no incluye la cotización de hoy, que sale de la red con una caché de 15 minutos. Es la condición que fijó el plan, y queda dicha acá.
  * Se guardan solo los días que pidió algún rango. Un rango nuevo vuelve a traer la serie, aunque la caché lo evita durante 15 minutos.
  * El total de una categoría y el de su mes se redondean por separado. Pueden diferir en un centavo de la suma de sus partes.
  * Un pedido usa tres o cuatro conexiones del pool.
* Riesgos y cómo se mitigan:
  * **El runner de CI es más lento que la máquina local.** El margen local es de casi el doble. Si la prueba empieza a fallar sin cambios de código, se mide en el runner antes de tocar el límite: no se sube el número para que pase.
  * **La fuente cambia la forma de la serie.** Cada elemento se valida como dato no confiable, y uno inválido se descarta solo. Un cuerpo con otra forma cuenta como fuente caída.

## Supuestos y datos faltantes

* Hoy el arrastre es una red de seguridad: la serie trae todos los días de calendario (2.936 días del 2018-10-29 al 2026-11-11), así que la fuente ya completa fines de semana y feriados. Se supone que seis días cubren cualquier fin de semana largo con feriados puente. Si la fuente dejara huecos más largos, esos días quedarían sin cotización, a la vista, y el tope se revisaría con el calendario de feriados en la mano.
* Se supone que 24 meses alcanzan para un dashboard. Para períodos más largos, como un reporte anual de varios años, conviene sumar por mes en la base y convertir con un criterio mensual explícito, en un ADR nuevo.
* No se midió con varias personas usando el dashboard a la vez. La medición es secuencial.

## Referencias

* [ADR-0001](0001-monolito-modular-fastapi-clean-architecture.md): monolito modular y regla de dependencias.
* [ADR-0005](0005-hosting-gratuito.md): hosting gratuito, sin planificador.
* [ADR-0016](0016-fuentes-de-cotizaciones.md): fuentes de cotizaciones e histórico.
* [ADR-0017](0017-conversion-al-consultar.md): conversión al consultar y regla prudente.
* ArgentinaDatos, serie del MEP: `https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa`, consultada el 2026-11-11.
