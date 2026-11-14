# ADR-0025: Pesos constantes con el IPC del INDEC

* **Estado:** Aceptado
* **Fecha:** 2026-11-14

## Contexto

La fase 7 pide reportes en pesos constantes. Con inflación mensual de dos puntos, $100.000 de enero y $100.000 de octubre no son la misma plata. Comparar meses en pesos corrientes muestra un gasto que "sube" aunque se compre lo mismo.

Hechos verificados el 2026-11-14:

* El INDEC publica el IPC nacional, nivel general, base diciembre de 2016. La API de series de tiempo del Estado (`apis.datos.gob.ar`) lo expone como la serie `148.3_INIVELNAL_DICI_M_26`.
* Esa serie trae el **índice**, con cuatro decimales y un valor por mes: 119 meses, de diciembre de 2016 a octubre de 2026. Entera pesa unos pocos KB y sale en un solo pedido.
* ArgentinaDatos, que ya es fuente de cotizaciones (ADR-0016), publica la inflación como **variación mensual** con un decimal (por ejemplo, 2,2 %).
* El INDEC publica el IPC de un mes a mediados del mes siguiente. El 14 de noviembre ya está octubre; noviembre sale en diciembre.

Restricciones: nada de valores inventados (ADR-0018), redondeo solo en los bordes, ninguna cuenta de dinero en el frontend, módulos que se leen por su capa de aplicación (ADR-0001), hosting sin planificador (ADR-0005).

## Opciones consideradas

### Fuente

#### Opción A: variación mensual de ArgentinaDatos
* Pros: una fuente que ya usamos.
* Contras:
  * Con un decimal, cada mes puede errar hasta 0,05 puntos. Encadenados 24 meses, el error llega a más de un punto del total.
  * No es la fuente primaria: es una copia del dato del INDEC.

#### Opción B: el índice en la API de series del Estado
* Pros:
  * Es el dato del INDEC, publicado por el Estado, con cuatro decimales.
  * El factor entre dos meses es una división de dos índices: no se encadena nada.
* Contras: una fuente externa más, sin respaldo. Si no responde, se usa lo guardado.

### Qué se ajusta

#### Opción A: todo el dashboard
* Contras: el patrimonio ya está al cierre de cada mes. Ajustarlo mezcla dos preguntas distintas, y el gasto por categoría es una suma de varios meses: un mes sin IPC la dejaría incompleta.

#### Opción B: solo el flujo de cada mes
* Pros: es la comparación que distorsiona la inflación, y cada mes se ajusta solo o queda vacío, sin totales a medias.
* Contras: el gasto por categoría sigue en pesos corrientes. La pantalla lo tiene que decir.

### Dónde vive el IPC

#### Opción A: dentro de cotizaciones
* Contras: una cotización es de un día y de un tipo de dólar; el IPC es mensual y no tiene compra ni venta. Mezclaría dos modelos en un módulo.

#### Opción B: un módulo `inflation`
* Pros: su propio modelo, su tabla y su fuente. No depende de ningún otro módulo y el dashboard lo lee por su capa de aplicación, como a cotizaciones.
* Contras: más contratos de import-linter y otra fábrica en la raíz de composición.

## Decisión

Índice del INDEC por la API de series (fuente B), solo el flujo mensual (B) y un módulo `inflation` (B). Es el dato primario, el que no acumula error, y el ajuste que nunca deja un total a medias.

**1. La cuenta.**
* Pesos del mes base = monto del mes × índice base ÷ índice del mes.
* El mes base es el último mes publicado, no el último del período: "pesos de hoy" es el poder de compra más reciente que se conoce.
* Se ajusta la suma del mes sin redondear, ya convertida a pesos con la cotización de cada día (ADR-0018). El factor es el mismo para todo el mes, así que da lo mismo que ajustar cada movimiento.
* Se redondea una vez cada número que se muestra, con `ROUND_HALF_EVEN`. El neto es la resta de los dos redondeados, igual que en pesos corrientes.
* El índice es un promedio del mes: un gasto del 1 y uno del 30 se ajustan igual. Es la convención del propio INDEC.

**2. Nada inventado.**
* Un mes sin índice publicado (el mes en curso, el anterior antes de mediados de mes, o antes de diciembre de 2016) queda vacío, no con el factor 1.
* Si no hay ningún índice guardado y la fuente no responde, no hay mes base y todo el ajuste queda vacío.

**3. Solo en pesos.** El IPC mide los precios en pesos. Pedir pesos constantes con otra moneda de referencia es un error (`DASHBOARD_CONSTANT_PRICES_ARS_ONLY`), no un número que no significa nada.

**4. Cómo se llena.**
* Lo publicado se guarda en `cpi_months`, un mes por fila, y nunca se pisa: el valor que se usó para un reporte sigue ahí para auditarlo.
* Si a un rango le falta un mes que ya debería estar publicado, o el último guardado es anterior al mes pasado, se trae la serie completa y se guarda lo que faltaba.
* La serie queda en memoria una hora. Del 1 al 15 de cada mes el mes pasado todavía no está, y sin la caché cada pedido iría a la fuente.
* Se pide con la misma política que las cotizaciones: tiempo máximo de 3 segundos, un reintento con espera, tope de tamaño y cada elemento validado como dato no confiable. Un mes futuro, repetido, en cero o negativo se descarta.

**5. A pedido.** El ajuste se pide con `prices=constant`. Sin eso, el dashboard no consulta el IPC y no cambia en nada lo que mide la prueba de rendimiento.

## Consecuencias

* Positivas:
  * La comparación entre meses deja de estar inflada, con el dato oficial y sin error acumulado.
  * Cada factor se puede rehacer a mano con dos filas de `cpi_months`.
* Negativas / costos aceptados:
  * El mes en curso nunca aparece en pesos constantes, y el anterior tampoco hasta mediados de mes. Es lo honesto, pero es el mes que más interesa.
  * El gasto por categoría queda en pesos corrientes.
  * Una fuente externa más, sin respaldo.
  * El índice es nacional; la inflación de cada región y de cada persona es otra.
* Riesgos y cómo se mitigan:
  * **La API cambia de forma o deja de publicar la serie.** Un cuerpo con otra forma cuenta como fuente caída: se sigue con lo guardado y los meses nuevos quedan vacíos, a la vista.
  * **El INDEC cambia de base.** Una base nueva es otra serie con otros valores. Mezclarlas daría factores falsos, así que el cambio requiere un ADR y una migración de la tabla, no un cambio de identificador.

## Supuestos y datos faltantes

* Se supone que el INDEC no revisa un mes ya publicado del IPC nacional. Si lo hiciera, el valor guardado sería el primero, y la diferencia se vería comparando con la fuente.
* No se midió cuánto tarda la fuente desde el hosting de producción.

## Referencias

* [ADR-0001](0001-monolito-modular-fastapi-clean-architecture.md): monolito modular.
* [ADR-0016](0016-fuentes-de-cotizaciones.md): política de fuentes externas.
* [ADR-0018](0018-modelo-de-lectura-del-dashboard.md): modelo de lectura del dashboard y redondeo.
* INDEC, Índice de precios al consumidor: `https://www.indec.gob.ar/indec/web/Nivel4-Tema-3-5-31`.
* Serie en la API del Estado: `https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26`, consultada el 2026-11-14.
