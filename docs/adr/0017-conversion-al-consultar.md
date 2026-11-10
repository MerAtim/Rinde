# ADR-0017: Conversión al consultar y preferencias de referencia

* **Estado:** Acepta y reemplaza en parte a ADR-0002 (el snapshot de conversión por transacción)
* **Fecha:** 2026-11-10

## Contexto

ADR-0002 decidió que cada transacción guardaría, opcionalmente, una foto de la cotización con que se convirtió: tasa, tipo, fuente y fecha. Lo que buscaba era que los reportes fueran reproducibles: que un gasto de hace un año no cambiara de valor cada día.

Desde ADR-0016 hay un hecho nuevo: Rinde guarda la cotización de cada día cerrado, con su fuente, y esa fila no se pisa nunca. Convertir un monto con la cotización de su fecha da siempre el mismo resultado, se haga hoy o dentro de un año.

Hace falta decidir además en qué moneda se muestran los totales y con qué dólar se convierte, porque en Argentina no hay "el" dólar (ADR-0002).

Restricciones: nunca un valor inventado; redondeo solo en los bordes; nada de aritmética de dinero en el frontend.

## Opciones consideradas

### Opción A: foto de la cotización en cada operación (lo que decía ADR-0002)
* Pros: cada operación lleva consigo con qué se convirtió, aunque se borre el histórico.
* Contras:
  * Es una columna más por operación, más la migración de las que ya existen.
  * Copia un dato que ya está, inmutable, en `exchange_rates`.
  * Si la persona cambia el dólar de referencia, lo viejo queda convertido con el anterior: un mismo reporte mezcla dólares distintos.

### Opción B: convertir al consultar, con el histórico guardado
* Pros:
  * Un solo lugar para cada cotización.
  * Cambiar el dólar de referencia recalcula todo con el mismo criterio.
  * No toca el modelo de movimientos (ADR-0011) ni el de transferencias (ADR-0014).
* Contras:
  * Cada reporte tiene que buscar las cotizaciones de las fechas que muestra.
  * Si una fuente no tiene un día, ese monto queda sin equivalente hasta que lo tenga.

## Decisión

Opción B. El histórico inmutable ya da la reproducibilidad que buscaba ADR-0002, sin duplicar datos y sin mezclar criterios cuando cambia la preferencia.

Las transferencias entre monedas no cambian: ya guardan los dos montos, que son la tasa real de esa operación (ADR-0014).

**Qué precio se usa.** El de lo que de verdad podrías hacer en el mercado, siempre del lado prudente: nunca se valúa de más lo que tenés ni de menos lo que debés.

| Monto | A pesos | A dólares |
|---|---|---|
| Dólares que tenés | compra (los venderías) | |
| Dólares que debés | venta (tenés que comprarlos) | |
| Pesos que tenés | | venta (comprarías dólares) |
| Pesos que debés | | compra (venderías dólares para cancelar) |

Ida y vuelta nunca se termina con más de lo que se tenía; una prueba generativa lo verifica. El redondeo es uno solo, al final, `ROUND_HALF_EVEN` a la precisión de la moneda de destino.

**Preferencias.** Cada persona elige la moneda de los totales (pesos o dólares) y el dólar con que se convierte. Sin elegir nada, pesos al MEP: es el dólar legal al que se opera sin cupo, el más usado para valuar ahorros. Bitcoin no puede ser la moneda de los totales ni se convierte todavía, porque no tiene cotización (ADR-0016).

El tipo de dólar pasa al kernel compartido: lo publican las cotizaciones y lo guardan las preferencias, y un módulo no puede depender del dominio de otro.

## Consecuencias

* Positivas:
  * La conversión es una función pura del dominio, probada sin base ni red.
  * El endpoint `GET /api/rates/{rate_type}/conversion` sirve para cualquier pantalla. Cuentas ya lo usa para mostrar el equivalente de cada saldo.
  * Las preferencias son un módulo propio, sin dependencias de otros módulos.
* Negativas / costos aceptados:
  * Un saldo sin cotización ese día se muestra sin equivalente. La pantalla lo dice.
  * Hoy el equivalente se pide de a una cuenta. Con pocas cuentas en otra moneda alcanza; el dashboard (fase 4) va a necesitar convertir muchos montos de una vez, y ahí se suma un endpoint por lote.
  * La pregunta de ADR-0002 sobre el dólar tarjeta sigue abierta: hoy un gasto con tarjeta en dólares se convierte con el dólar elegido en preferencias, no con el del resumen.
* Riesgos y cómo se mitigan:
  * **Se corrige una cotización ya guardada:** hoy no pasa, porque las filas no se pisan (ADR-0016). Si algún día se permitiera, los reportes viejos cambiarían; para eso habría que versionar las cotizaciones, no volver a la foto por operación.

## Supuestos y datos faltantes

* Se asume que la regla prudente es la que una persona espera ver. Si en el uso real resulta confusa, se puede mostrar el precio medio, documentándolo en un ADR nuevo.
* Las descripciones de cada dólar en la pantalla de preferencias son de uso común, no definiciones normativas.

## Referencias

* [ADR-0002](0002-representacion-de-dinero-y-cotizaciones.md): dinero y cotizaciones múltiples.
* [ADR-0014](0014-modelo-de-transferencias.md): transferencias entre monedas.
* [ADR-0016](0016-fuentes-de-cotizaciones.md): fuentes de cotizaciones e histórico.
