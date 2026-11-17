# ADR-0030: Gastos en dólares con tarjeta: se valúan con el dólar de referencia, y el pago guarda lo que se pagó

* **Estado:** Aceptado
* **Fecha:** 2026-11-17

## Contexto

ADR-0002 dejó una pregunta abierta, que ADR-0016 y ADR-0017 arrastraron: un gasto en dólares con tarjeta, ¿se valúa al dólar tarjeta o al del resumen? Hoy se convierte con el dólar que cada persona elige en preferencias (ADR-0017), como cualquier otro monto.

Hechos:

* Cada cuenta tiene una sola moneda (ADR-0009). Los consumos en dólares de una tarjeta argentina van a una cuenta tarjeta en dólares, separada de la de pesos.
* Una transferencia entre cuentas de distinta moneda guarda los dos montos tal como los carga la persona, sin cotización: es la tasa real de esa operación (ADR-0014, decisión 3). Cancelar en pesos el saldo en dólares de la tarjeta es una transferencia de la cuenta en pesos a la tarjeta en dólares.
* Una transferencia no es ni gasto ni ingreso (ADR-0014).
* El dólar tarjeta es el oficial vendedor del Banco Nación más la percepción del 30 % de la RG 5617/2024 de ARCA, que reemplazó al impuesto PAIS en diciembre de 2024. Se cobra sobre lo que se paga en pesos; pagar el saldo con dólares propios la evita.
* La percepción es un pago a cuenta de Ganancias o Bienes Personales. Quien no paga esos impuestos puede pedir la devolución a ARCA.
* Algunos emisores (billeteras con tarjeta propia) informan que no aplican la percepción. Las fuentes consultadas no coinciden del todo sobre los detalles, y la norma puede cambiar.

## Opciones consideradas

### Opción A: un solo dólar para todo, el de referencia
* Pros:
  * Un mismo reporte usa un solo criterio, como pide ADR-0017.
  * No depende de cómo se pague el resumen, que Rinde no sabe de antemano.
  * Lo que se pagó de verdad ya queda registrado, exacto, en la transferencia del pago.
  * No cambia código ni datos.
* Contras:
  * Si se paga en pesos, el gasto en el presupuesto queda por debajo de los pesos que salieron, en la medida de la percepción.

### Opción B: los gastos en dólares de una cuenta tarjeta se valúan al dólar tarjeta
* Pros: se parece a lo que sale del bolsillo cuando se paga en pesos.
* Contras:
  * Un mismo total mezcla dos dólares, y cambiar la preferencia ya no recalcula todo con el mismo criterio.
  * Cuenta como gasto la percepción, que es un crédito fiscal.
  * Exagera el costo cuando el resumen se paga con dólares propios, o con un emisor sin percepción.

### Opción C: cada cuenta tarjeta indica si se paga en pesos o en dólares
* Pros: es lo más fiel para cada caso.
* Contras:
  * Un campo nuevo con su migración, su pantalla y un caso más en cada conversión del dashboard y de presupuestos.
  * La forma de pago puede cambiar de un mes a otro, y el campo queda desactualizado sin aviso.
  * Hereda los contras de B cuando dice "pesos".

## Decisión

Opción A. El gasto se valúa con el dólar de referencia, igual que todo lo demás, y el costo real del pago en pesos queda en la transferencia, que es un dato cargado y no uno estimado.

La percepción no es un gasto. Quien no pueda recuperarla y quiera verla en sus gastos la registra como un gasto en pesos (por ejemplo, en una categoría de impuestos) y transfiere a la tarjeta el resto.

## Consecuencias

* Positivas:
  * Se cierra la pregunta de ADR-0002 sin tocar el modelo ni la conversión.
  * Los reportes siguen siendo reproducibles y con un solo criterio (ADR-0017).
* Negativas / costos aceptados:
  * Al pagar en pesos, los pesos de más que se lleva la percepción bajan el patrimonio pero no aparecen como gasto en ningún reporte, salvo que la persona los cargue aparte.
  * Un presupuesto en pesos que incluya consumos en dólares de la tarjeta muestra menos de lo que va a costar si el resumen se paga en pesos.
* Riesgos y cómo se mitigan:
  * **Cambia la norma** (sube, baja o desaparece la percepción): la decisión no depende del porcentaje, porque Rinde no lo aplica en ningún lado.
  * **Una persona espera ver el dólar tarjeta en sus gastos:** el README explica cómo se valúan y cómo cargar la percepción. Si el uso real muestra que confunde, la opción C se puede sumar en un ADR nuevo sin migrar datos existentes.

## Supuestos y datos faltantes

* Se asume que la mayoría de quienes usan Rinde pueden computar o pedir la devolución de la percepción. Si no fuera así, el costo aceptado pesa más y habría que revisar la opción C.
* No hay un caso real de uso que confirme qué esperan ver; ADR-0002 lo pedía. Se decidió con la persona usuaria y queda abierto a revisión con datos.

## Referencias

* [ADR-0002](0002-representacion-de-dinero-y-cotizaciones.md): la pregunta original.
* [ADR-0009](0009-modelo-de-cuentas.md): una moneda por cuenta.
* [ADR-0014](0014-modelo-de-transferencias.md): transferencias entre monedas.
* [ADR-0017](0017-conversion-al-consultar.md): conversión al consultar y dólar de referencia.
* ARCA, RG 5617/2024 y modificatorias (texto actualizado en argentina.gob.ar).
* [iProfesional: dólar tarjeta y la percepción del 30 %](https://www.iprofesional.com/impuestos/445594-dolar-tarjeta-paso-a-paso-para-no-pagar-la-percepcion-del-30-por-ciento-de-arca-ex-afip).
* [Monarca: devolución de percepciones](https://askmonarca.com/guias/percepciones-exterior).
