# ADR-0016: Fuentes de cotizaciones y cómo se llena el histórico

* **Estado:** Aceptado
* **Fecha:** 2026-11-10

## Contexto

ADR-0002 decidió que las cotizaciones se piden a través de un puerto `RateProvider`, con varias fuentes, respaldo entre ellas, caché y un histórico propio. Dejó pendiente verificar las fuentes antes de implementar. Este ADR registra esa verificación y cómo se combinan las fuentes.

Hechos verificados el 2026-11-10, pidiendo a cada fuente:

* **DolarAPI** (`dolarapi.com`, licencia MIT): publica oficial, blue, MEP (`bolsa`), CCL, mayorista, cripto y tarjeta, con compra, venta y momento de actualización. Solo el último valor, sin histórico.
* **ArgentinaDatos** (`api.argentinadatos.com`): los mismos tipos y nombres, día por día. Oficial, blue y mayorista desde 2011; CCL desde 2013; MEP desde 2018; tarjeta desde 2019; cripto desde 2023. Para una fecha sin dato responde 404. Los fines de semana y feriados repite el último valor hábil y no informa la hora.
* **DolarAPI y ArgentinaDatos son del mismo autor.** Pueden fallar juntas.
* **CriptoYa** (`criptoya.com/api/dolar`): oficial y blue con compra y venta, que coincidían con los de DolarAPI (1520/1570 y 1535/1555). El MEP y el CCL los publica por bono (AL30, GD30...), con un solo precio y sin compra ni venta: no es el mismo dato. El tarjeta, con un solo precio.
* **Bluelytics**: solo oficial y blue.
* **BCRA, estadísticas cambiarias**: el "oficial" es el mayorista de la Comunicación A 3500 (1545,5 ese día), no el minorista de Banco Nación (1570). Es otro dólar con el mismo nombre.
* Ninguna publica términos de uso ni límites de pedidos.
* El oficial de DolarAPI de ese día era del 5 de noviembre: después de un feriado, "hoy" puede ser un día hábil anterior.
* La API corre en una instancia gratuita de Render que se suspende a los 15 minutos sin tráfico (ADR-0005).

Restricciones: nunca mostrar un valor inventado ni un dólar en lugar de otro; seguro por defecto; costo cero.

## Opciones consideradas

### Opción A: un proceso que baja las cotizaciones cada cierto tiempo
* Pros: la página nunca espera a una fuente. El histórico se llena aunque nadie lo pida.
* Contras: en Render el proceso se duerme con la API, así que no correría. Llevarlo a un cron de GitHub Actions exige un endpoint de escritura expuesto en internet y un secreto más. Guarda datos que nadie mira.

### Opción B: cargar todo el histórico de ArgentinaDatos de una vez
* Pros: después no hay que pedirle nada a nadie para días pasados.
* Contras: unas 30.000 filas que casi nadie va a consultar. Igual hace falta otra cosa para el valor de hoy y para los días que vengan.

### Opción C: pedir a demanda, con caché y guardando los días cerrados
* Pros: no depende de que la API esté despierta. Un día pasado se pide una sola vez y después sale de la base. No hay nada programado ni ningún secreto nuevo.
* Contras: la primera consulta de un día pasado espera a la fuente (hasta seis pedidos en paralelo, uno por tipo). Si todas las fuentes están caídas, hoy no hay cotización.

## Decisión

Opción C, con esta cadena de fuentes, en este orden:

1. **DolarAPI**, para hoy: un solo pedido trae los seis tipos.
2. **ArgentinaDatos**, para cualquier día. Es la única fuente de días pasados, y la única además de DolarAPI que publica MEP, CCL, tarjeta y cripto. Por eso va antes que CriptoYa, aunque sea del mismo autor que DolarAPI.
3. **CriptoYa**, solo para el oficial y el blue de hoy: es la fuente independiente de las otras dos.

Reglas:

* **Un tipo solo se reemplaza por el mismo tipo.** Cada adaptador traduce únicamente los dólares que su fuente publica con la misma definición. El BCRA y Bluelytics quedan afuera: el primero no tiene el mismo oficial y el segundo no suma nada que CriptoYa no cubra.
* **Hoy no se guarda.** La cotización de hoy se sigue moviendo: sale de las fuentes, con 15 minutos de caché en memoria. Un día ya cerrado se guarda la primera vez que se pide, y la fila no se pisa nunca.
* **Lo que no está, no está.** Si ninguna fuente tiene un tipo para ese día, no aparece y el endpoint de un solo tipo responde `RATE_NOT_FOUND`. Si no responde ninguna y no hay nada guardado, `RATES_UNAVAILABLE` (503).
* **Se muestra la fecha real.** La respuesta lleva `updated_at` cuando la fuente lo informa, y la pantalla avisa si no es de hoy.
* **Validación de lo que llega.** El JSON se lee con los números como `Decimal`, sin pasar por `float`. Se descartan los elementos con valores no positivos, compra mayor que venta, más de 16 dígitos enteros, fecha sin zona horaria o un "último valor" de hace más de 6 días. Se descartan también las respuestas de más de 256 KB. Un elemento descartado no tira abajo el resto de la respuesta.
* **Tiempos.** 3 segundos por pedido y un reintento con espera ante errores de red y 502, 503 o 504. Un 429 no se reintenta: se pasa a la fuente siguiente.
* **El día es el de Argentina** (`America/Argentina/Buenos_Aires`), no el de UTC: a las 22 de Buenos Aires ya es el día siguiente en UTC.
* **Los endpoints piden sesión**, aunque las cotizaciones son las mismas para todos, para que nadie use Rinde como intermediario gratis contra las fuentes.

## Consecuencias

* Positivas:
  * Funciona en el plan gratuito sin piezas programadas.
  * Cada número guardado dice de qué fuente salió y cuándo se trajo (`fetched_at`): se puede auditar.
  * La conversión de la segunda parte de la fase 3 ya tiene su caso de uso (`GetQuote`).
* Negativas / costos aceptados:
  * Para días pasados hay una sola fuente. Si ArgentinaDatos se cae, un día que no esté guardado no se puede consultar hasta que vuelva.
  * DolarAPI y ArgentinaDatos se pueden caer juntas. Ese día solo quedan el oficial y el blue de CriptoYa.
  * Un fin de semana, ArgentinaDatos repite el valor del viernes sin decirlo, y para días pasados no informa la hora. Se guarda tal cual y `updated_at` queda vacío.
  * La caché es por proceso y tiene un solo candado: mientras un pedido consulta las fuentes, los demás esperan. Con el tráfico actual alcanza; con varias instancias, cada una tendría su propia caché.
  * Quien tenga sesión puede recorrer fechas y generar pedidos a ArgentinaDatos. Hay un tope: cada día se guarda una vez y la caché también recuerda los "no hay dato".
  * Un dato con la compra por encima de la venta se descarta, aunque alguna vez pudiera ser real.
* Riesgos y cómo se mitigan:
  * **Una fuente cambia su formato:** la validación lo detecta, se descarta y responde la siguiente. Queda un aviso en el log con el nombre de la fuente.
  * **Una fuente cierra o empieza a cobrar:** cada una es un adaptador de unas 40 líneas detrás del mismo puerto. Reemplazarla no toca el dominio ni la API.
  * **Una fuente se traba y repite un valor viejo como si fuera de hoy:** se descarta pasados 6 días, y antes de eso la pantalla muestra la fecha real.

## Supuestos y datos faltantes

* Se asume que el valor de ArgentinaDatos para un día ya cerrado es definitivo. Si se descubre que lo corrige después, habría que permitir reemplazar filas recientes.
* Se asume que el oficial y el blue de CriptoYa son los mismos que los de DolarAPI. Coincidían el día de la verificación; no hay una definición publicada que lo confirme.
* Sigue abierta la pregunta de ADR-0002 sobre el dólar tarjeta: si un gasto en dólares con tarjeta se registra al tipo tarjeta o al del resumen. Se decide en la segunda parte de la fase, con la conversión.
* El precio del Bitcoin (par BTC/USD) no está cubierto. Requiere verificar CoinGecko u otra fuente.

## Referencias

* [ADR-0002](0002-representacion-de-dinero-y-cotizaciones.md): dinero y cotizaciones múltiples.
* [ADR-0005](0005-hosting-gratuito.md): hosting gratuito.
* [DolarAPI](https://dolarapi.com) · [ArgentinaDatos](https://argentinadatos.com) · [CriptoYa](https://criptoya.com)
* [Estadísticas cambiarias del BCRA](https://www.bcra.gob.ar/BCRAyVos/catalogo-de-APIs-banco-central.asp)
