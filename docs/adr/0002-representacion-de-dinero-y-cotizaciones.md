# ADR-0002: Representación de dinero y cotizaciones múltiples

* **Estado:** Propuesto
* **Fecha:** 2026-09-11

## Contexto

El mercado objetivo es Argentina/LatAm. Hechos del dominio:

* Para una misma fecha conviven varias cotizaciones del dólar (oficial, MEP, CCL, blue, tarjeta, cripto) que pueden diferir entre sí de forma significativa.
* Los montos históricos pierden sentido en pesos nominales por la inflación.
* Los criptoactivos requieren más de 2 decimales (BTC: 8).
* `float` no representa exactamente valores decimales como 0.1: acumula error.

La premisa dice "conversión en tiempo real". Para finanzas personales lo relevante es la **tasa de la fecha de la operación**, no la de este instante. "Tiempo real" solo tiene sentido para la valuación actual del patrimonio.

## Opciones consideradas

### Opción A: `Decimal` + `NUMERIC(24,8)` + snapshot de conversión por transacción
* Pros: exacto, cubre fiat y cripto, los reportes históricos son reproducibles.
* Contras: más columnas y más lógica; ETH (18 decimales) se trunca a 8.

### Opción B: enteros en unidad mínima (centavos)
* Pros: rápido, simple para fiat.
* Contras: el exponente varía por moneda y por activo; mezclarlos complica todo. Errores de escala silenciosos.

### Opción C: convertir siempre con la tasa actual al mostrar
* Pros: trivial.
* Contras: incorrecto. El gasto de hace un año "cambia" de valor cada día y los reportes no son reproducibles.

## Decisión

Opción A:

* Objeto de valor `Money(amount: Decimal, currency: Currency)` inmutable. La precisión la define cada moneda (ARS/USD: 2, BTC: 8).
* La transacción guarda el monto original y su moneda, y opcionalmente un `ConversionSnapshot(rate, rate_type, source, as_of)`.
* `RateType` es un concepto de dominio (`OFICIAL`, `MEP`, `CCL`, `BLUE`, `TARJETA`, `CRIPTO`). El usuario elige cuál usar como referencia en sus reportes.
* Tabla histórica de cotizaciones por (fecha, par, tipo, fuente) para reportes y reconstrucción.
* El ajuste por inflación (pesos constantes) se calcula en consulta a partir de una serie de IPC, sin modificar los datos guardados.

## Consecuencias

* Positivas: reportes reproducibles; el análisis "cuánto gasté en dólares MEP" es un diferencial real y verificable.
* Negativas / costos aceptados: ETH y tokens con más de 8 decimales se truncan (aceptable para seguimiento personal, inaceptable para contabilidad on-chain); más complejidad en el modelo.
* Riesgos: dependencia de APIs no oficiales sin SLA para cotizaciones paralelas. Mitigación: puerto `RateProvider` con varios adaptadores, cadena de fallback, caché y persistencia del histórico propio.

## Supuestos y datos faltantes

* **Verificar antes de implementar** disponibilidad, términos de uso y límites de: DolarAPI, ArgentinaDatos (histórico), API de estadísticas cambiarias del BCRA (oficial), CoinGecko (cripto), API de series de datos.gob.ar (IPC INDEC).
* No se sabe aún si el usuario final registra el gasto en tarjeta en USD al tipo "tarjeta" o al del resumen. Hay que decidirlo con un caso real.

## Referencias

* ISO 4217 (códigos y exponentes de moneda).
