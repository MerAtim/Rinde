# ADR-0029: Precio del Bitcoin: Kraken con Bitstamp de respaldo, y conversión en dos pasos

* **Estado:** Aceptado
* **Fecha:** 2026-11-16

## Contexto

Una billetera cripto puede tener Bitcoin (ADR-0009), pero hasta ahora no tenía precio: el saldo no tenía equivalente en pesos ni en dólares, y el dashboard y los presupuestos lo informaban aparte, sin sumarlo (ADR-0018, ADR-0021). ADR-0016 dejó pendiente elegir la fuente.

Se decidió con la persona usuaria valuar el Bitcoin al **precio del mercado internacional**, con histórico diario, en lugar del precio de los exchanges argentinos.

Hechos verificados el 2026-11-16, con pedidos reales:

* **Kraken** (`api.kraken.com/0/public`): sin clave. `Ticker` da compra (`b`) y venta (`a`) de `XBTUSD`. `OHLC` con `interval=1440` da 721 velas diarias; cada una empieza a las 00:00 UTC de su día, y la última es la del día en curso, que todavía no cerró. Opera desde Estados Unidos, donde corre la API (ADR-0005).
* **Bitstamp** (`www.bitstamp.net/api/v2`): sin clave. `ticker/btcusd` da compra y venta; `ohlc/btcusd` con `step=86400` da hasta 1000 velas diarias con la misma convención. Su precio difería del de Kraken en unos 20 dólares sobre 64.500.
* **CoinGecko**: un solo precio promedio, sin compra ni venta. El plan gratuito pide clave y atribución; sin clave, los límites no están documentados.
* **CriptoYa**, ya usada para el dólar cripto: compra y venta de cada exchange argentino, con una brecha de alrededor de 5 % sobre el mercado internacional, pero sin histórico.
* El dólar que elige cada persona (`RateType`) vive en el kernel compartido porque lo guarda preferencias (ADR-0017).

## Opciones consideradas

### Opción A: el Bitcoin como un tipo de dólar más
* Pros: reutiliza todo el camino de los dólares sin cambios.
* Contras: preferencias permitiría elegir "Bitcoin" como el dólar con el que se convierte, que no tiene sentido. Mezcla dos preguntas distintas: cuántos dólares vale un Bitcoin y cuántos pesos vale un dólar.

### Opción B: el precio de los exchanges argentinos (CriptoYa)
* Pros: es lo que de verdad paga un exchange local, con su brecha.
* Contras: sin histórico. Los días pasados habría que valuarlos con el precio de hoy, contra la regla de que cada monto se convierte con la cotización de su día (ADR-0017), o dejarlos sin convertir.

### Opción C: precio internacional, como un mercado aparte, y conversión en dos pasos
* Pros: histórico diario, compra y venta reales, sin clave. El Bitcoin pasa a dólares con su precio y los dólares a pesos con el dólar que eligió la persona: las dos preguntas quedan separadas.
* Contras: no incluye la brecha de los exchanges locales. Depende de fuentes del exterior.

## Decisión

Opción C, que es la elegida. Respeta la conversión con el precio de cada día y no ensucia la elección del dólar.

**1. Un mercado, no un dólar.** Las cotizaciones distinguen dos clases: los dólares (`RateType`, sin cambios) y los mercados (`Market`, por ahora solo `BITCOIN`). El precio del Bitcoin es el par BTC/USD; los dólares siguen siendo USD/ARS. Se guarda en la misma tabla, y la base exige que la clase y el par vayan juntos.

**2. Fuentes.** Kraken primero y Bitstamp de respaldo, con la misma cadena y la misma caché que los dólares (ADR-0016), tanto para el precio de hoy como para el histórico. Se elige Bitstamp y no CoinGecko, que se había pensado primero: tiene compra y venta, histórico y no pide clave ni atribución. Toda respuesta se valida como entrada no confiable.

**3. Qué precio es cada día.** Hoy, la compra y la venta del ticker. Un día cerrado, el cierre de su vela diaria como compra y como venta, porque el histórico no informa las dos puntas. La vela que empieza a las 00:00 UTC del día D cierra a las 21 de Argentina del mismo D: es el precio de D. Solo se guardan días anteriores al de hoy en Argentina.

**4. Conversión en dos pasos.** Bitcoin a dólares con el precio del día, y, si hace falta, dólares a pesos con el dólar elegido del mismo día. Cada paso aplica la regla prudente de ADR-0017 según el signo, y se redondea una sola vez, al final. Si falta cualquiera de los dos precios, el monto no se convierte y se informa aparte, como hasta ahora.

**5. Lo que cambia para quien usa la app.** El saldo de una billetera en Bitcoin muestra su equivalente. El dashboard suma el Bitcoin al patrimonio. Un gasto en Bitcoin cuenta en su presupuesto: ADR-0021 lo dejaba afuera solo porque no tenía cotización. La conversión de la API informa cada paso con su cotización.

## Consecuencias

* Positivas:
  * Un patrimonio con Bitcoin se ve completo, convertido con el precio de cada día.
  * La elección del dólar no cambia: el Bitcoin la usa en su segundo paso.
  * El mismo mecanismo sirve para otro criptoactivo, si algún día se agrega.
* Negativas / costos aceptados:
  * No refleja la brecha de alrededor de 5 % de los exchanges argentinos: el Bitcoin queda valuado algo por encima de lo que pagaría uno local.
  * Para días pasados, compra y venta son el mismo precio: la regla prudente se aplica completa solo hoy.
  * Dos fuentes nuevas del exterior; si las dos fallan, el Bitcoin vuelve a quedar sin convertir hasta el pedido siguiente.
* Riesgos y cómo se mitigan:
  * **Una fuente cambia su formato.** La validación estricta rechaza la respuesta y contesta la siguiente; los tests fijan el formato esperado.
  * **Un día sin vela** (una caída de la fuente): se arrastra el último precio hasta el mismo tope que los dólares (ADR-0018).

## Supuestos y datos faltantes

* Se supone que el cierre de las 21 de Argentina representa bien el día: el Bitcoin opera todo el día y no tiene un cierre oficial.
* Si se quisiera la brecha local, se podría aplicar al precio de hoy con CriptoYa; queda para otro ADR si alguien lo pide.

## Referencias

* [ADR-0009](0009-modelo-de-cuentas.md): Bitcoin solo en billeteras cripto.
* [ADR-0016](0016-fuentes-de-cotizaciones.md): cadena de fuentes y caché.
* [ADR-0017](0017-conversion-al-consultar.md): conversión al consultar y regla prudente.
* [ADR-0018](0018-modelo-de-lectura-del-dashboard.md): histórico por serie y arrastre de días sin cotización.
* [ADR-0021](0021-modelo-de-presupuestos.md): presupuestos.
* Kraken, OHLC: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data
* Bitstamp, API v2: https://www.bitstamp.net/api/
