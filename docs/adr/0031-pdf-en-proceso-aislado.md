# ADR-0031: La lectura de un PDF corre en un proceso aislado con topes

* **Estado:** Aceptado
* **Fecha:** 2026-11-18

## Contexto

La importación lee el resumen PDF que sube la persona (ADR-0023). Ya se miraba la firma, se contaban las páginas antes de leer y el archivo llegaba acotado a 1 MB. Faltaba un tope a lo que el archivo puede inflarse al leerse.

Hechos medidos el 2026-11-18:

* Un PDF guarda su contenido comprimido. Uno de 200 kB armado a propósito se infló a 374 MB de memoria al leerlo con pdfplumber.
* Uno de 996 kB, dentro del límite de 1 MB, se infla a 1000 MB. La instancia de producción tiene 512 MB (ADR-0005): un solo pedido la tumba.
* La demo no pide registrarse (ADR-0028), así que cualquiera puede llegar a la importación.
* pdfminer, debajo de pdfplumber, descomprime con `zlib.decompress` entero y no tiene un tope propio.

Es una bomba de descompresión (CWE-409). OWASP recomienda tratar el procesamiento de archivos subidos como no confiable y aislarlo con límites de recursos.

## Opciones consideradas

### Opción A: revisar el PDF antes de leerlo y rechazar lo que se infla demasiado
* Pros: un solo proceso y sin costo de arranque.
* Contras:
  * Hay que recorrer los objetos del PDF con un parser propio o con el de pdfminer, que descomprime sin tope al cargar las tablas y los flujos de objetos.
  * Cada filtro (Flate, LZW, RunLength) y cada forma de anidarlos es un caso a cubrir, y uno olvidado vuelve a abrir el hueco.

### Opción B: leer en un proceso aparte con topes del sistema operativo
* Pros:
  * El tope vale para cualquier forma de inflar el archivo, conocida o no, y también para un error de pdfminer que consuma memoria o CPU.
  * Si el proceso se pasa, muere solo él. La API sigue en pie.
  * No toca el lector: es un Decorator sobre el mismo puerto.
* Contras:
  * Cada lectura arranca un intérprete nuevo, que suma segundos en la CPU chica de producción.
  * Los topes de memoria y de CPU son de Linux.

### Opción C: achicar el límite de tamaño del archivo
* Pros: un cambio de una línea.
* Contras: no cierra nada. La proporción de una bomba es de alrededor de mil a uno, y un resumen real de varias páginas tiene que seguir entrando.

## Decisión

Opción B. Es la única que pone un tope a la memoria sin depender de conocer cada forma de ataque.

`SandboxedPdfText` envuelve a `PdfPlumberText` y lo corre en un proceso nuevo (`spawn`, que no hereda la memoria ni las conexiones de la API), con estos topes:

* memoria: 192 MB por encima de lo que el proceso ocupa al empezar (`RLIMIT_AS`);
* CPU: 20 segundos (`RLIMIT_CPU`);
* reloj: 30 segundos, después de los cuales se mata el proceso;
* de a una lectura por vez, para que varias juntas no sumen sus topes.

Si cualquiera se supera, la API responde `IMPORT_PDF_INVALID`, el mismo código que un PDF dañado.

## Consecuencias

* Positivas:
  * Una bomba de 996 kB que se infla a 1000 MB se rechaza en unos 6 segundos, y el proceso de la API no pasa de 49 MB. Verificado en la imagen de producción con 512 MB.
  * Una prueba lo verifica en la CI, en Linux.
* Negativas / costos aceptados:
  * Importar un PDF tarda unos segundos más por el arranque del proceso. Se importa poco, y se prefiere eso a que un pedido tumbe el servidor.
  * Dos personas importando a la vez esperan una a la otra.
  * En Windows, que es solo desarrollo, rigen el proceso aparte y el tope de tiempo, sin los topes de memoria y CPU.
* Riesgos y cómo se mitigan:
  * **El margen de 192 MB queda corto para un resumen real:** uno real se lee con pocos megas; si pasara, el error es el de PDF inválido y el margen se ajusta.
  * **Una actualización cambia cómo arranca el proceso nuevo:** las pruebas leen un resumen de verdad a través del proceso aislado.

## Supuestos y datos faltantes

* Se asume que la instancia de producción sigue teniendo 512 MB. Si crece, el margen puede subir.
* No se midió el arranque en la CPU de producción (0,1). Si resultara molesto, se puede dejar un proceso listo de antemano, sin cambiar los topes.

## Referencias

* [ADR-0023](0023-modelo-de-importacion.md): importación de movimientos.
* [ADR-0005](0005-hosting-gratuito.md): la instancia de producción.
* [ADR-0028](0028-cuenta-demo.md): la demo sin registro.
* OWASP, [File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).
* MITRE, [CWE-409: Improper Handling of Highly Compressed Data](https://cwe.mitre.org/data/definitions/409.html).
