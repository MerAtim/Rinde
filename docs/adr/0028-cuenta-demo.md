# ADR-0028: Cuenta demo, una por visita, que se borra sola

* **Estado:** Aceptado
* **Fecha:** 2026-11-15

## Contexto

La fase 8 pide una cuenta demo con datos realistas, para probar la app sin registrarse. Quien la abre (alguien que evalúa el portfolio) quiere ver pantallas con datos, y también cargar, editar y borrar.

Se decidió con la persona usuaria que **cada visita tiene su propia cuenta**.

Hechos del sistema actual:

* No hay tareas programadas: el plan gratuito de Render no las tiene (ADR-0005). Lo que vence se limpia en una escritura, como los intentos fallidos y la actividad por origen.
* La base gratuita de Neon tiene 0,5 GB (ADR-0005).
* Registrarse ya tiene límite por origen: 5 cuentas por hora (ADR-0007).
* Todas las tablas de datos de una persona tienen `owner_id` con `ON DELETE CASCADE` hacia `users`. Las auditorías de movimientos y de transferencias no tienen clave foránea, y un trigger impide borrar o cambiar sus filas (ADR-0011).
* Las categorías se siembran solas la primera vez que se listan.

## Opciones consideradas

### Opción A: una cuenta compartida que se resetea cada tanto
* Pros: un solo juego de datos; nada que limpiar salvo el reseteo.
* Contras:
  * Cada visita ve lo que cargó la anterior, y cualquiera puede romperla para todos hasta el próximo reseteo.
  * El reseteo es una tarea programada, y el hosting no las tiene.
  * Va contra la regla de que nadie ve datos de otra persona, aunque sean de prueba.

### Opción B: una cuenta compartida de solo lectura
* Pros: segura y sin limpieza.
* Contras: no se pueden probar los formularios, que es la mitad de lo que hay para mostrar. Hace falta un modo "solo lectura" en cada endpoint que escribe.

### Opción C: una demo sin backend, con la API simulada en el navegador
* Pros: cero riesgo para la base; funciona aunque la API esté dormida.
* Contras: lo que se muestra no es la app real. Las reglas del dominio (reparto de cuotas, conversión, alertas) habría que reimplementarlas en el navegador, y la demo dejaría de probar justo lo que se quiere probar.

### Opción D: una cuenta por visita, sembrada al crearse, que vence sola
* Pros:
  * Cada visita está aislada por las mismas reglas que cualquier cuenta: ningún endpoint nuevo de lectura ni de escritura.
  * Se prueba la app real, con su base y sus reglas.
  * El borrado es el de una cuenta: la cascada que ya existe.
* Contras:
  * Crear una demo escribe en la base sin autenticación: hay que limitarla.
  * Las demos ocupan lugar hasta que se borran.
  * La auditoría no se puede borrar: hay que decidir qué pasa con la de una cuenta que deja de existir.

## Decisión

Opción D. Es la elegida y no agrega ningún camino de acceso a datos: una demo es una cuenta más.

**1. Qué es una demo.** Una fila de `users` con `demo_expires_at`, dos horas después de crearse. En una cuenta común la columna es `NULL`.
* El nombre es `demo-` más diez caracteres al azar. El prefijo `demo-` queda reservado: no se puede registrar una cuenta con ese nombre.
* La contraseña y el código de recuperación son hashes de secretos al azar que no se guardan en ningún lado: nadie puede iniciar sesión ni recuperar una demo. Se entra solo con la sesión que se emite al crearla.
* La sesión vence con la demo, y la cookie también.

**2. Cómo se crea.** `POST /api/auth/demo`, con el encabezado CSRF y sin sesión: es auth el que crea cuentas y emite sesiones. En una transacción:
* Se toma un lock de transacción (`pg_advisory_xact_lock`): dos pedidos a la vez no pasan juntos el tope.
* Se borran las demos vencidas, con todo lo suyo.
* Se controlan los límites:
  * 3 demos por hora por origen. Pasado, 429 `TOO_MANY_ATTEMPTS` con `Retry-After`, como el registro.
  * Como mucho 100 demos a la vez en total. Pasado, 503 `DEMO_UNAVAILABLE` con `Retry-After`: no es culpa de quien pide, el servicio está lleno.
* Se crea la cuenta.

**3. Los datos sembrados.** Después de crear la cuenta se cargan los datos por la capa de aplicación de cada módulo, con las mismas reglas que si los cargara una persona: tres cuentas en pesos (una de ellas tarjeta) y una en dólares, tres meses de gastos e ingresos, transferencias (una entre monedas), una compra en cuotas, el alquiler y la prepaga como recurrentes, y presupuestos, uno de ellos cerca del tope para que se vea una alerta. Los montos y las descripciones son inventados; ninguno sale de un resumen real. Las fechas se calculan desde hoy.
* Auth no sabe qué es una cuenta ni un movimiento: declara un puerto, `DemoSeeder`, y lo implementa un módulo nuevo, `demo`, que escribe por la capa de aplicación de cuentas, movimientos y presupuestos. La raíz de composición los conecta, y import-linter impide que algún módulo dependa de `demo`.
* Cada módulo confirma en su propia transacción, así que la siembra no es atómica. Si falla a mitad de camino, no se emite la sesión: la cuenta queda incompleta, nadie puede entrar y se borra al vencer.
* La sesión se emite al final, cuando todo está cargado.

**4. Borrar una demo.** Borrar la fila de `users` borra todo por la cascada. Para la auditoría:
* Las tablas de auditoría pasan a tener clave foránea a `users` con `ON DELETE CASCADE`.
* El trigger sigue impidiendo cambiar o borrar filas, salvo borrar las de un dueño que ya no existe. Así la cascada pasa, y un `DELETE` directo sobre la auditoría sigue fallando, también desde `psql`.
* Es la misma regla que hará falta para borrar una cuenta común a pedido de su titular (Ley 25.326, art. 16): la auditoría protege la historia de los datos de una persona mientras la persona tiene datos.

**5. Lo que ve quien entra.** Un aviso fijo dice que es una demo y a qué hora se borra, con un enlace para crear una cuenta propia. El botón "Probar la demo" está en la pantalla de inicio de sesión.

## Consecuencias

* Positivas:
  * La demo es la app real; lo que funciona ahí funciona para cualquiera.
  * Ningún cambio en los endpoints que leen o escriben datos: el aislamiento es el de siempre, con sus tests de autorización.
  * El borrado de cuentas queda resuelto en la base para cuando se pida.
* Negativas / costos aceptados:
  * Si nadie crea demos, las vencidas siguen en la base hasta la próxima. Nadie puede entrar a ellas, y el tope acota cuántas hay.
  * Quien use muchas direcciones puede llenar las 100 y dejar sin demo a los demás durante dos horas. Es el mismo riesgo que tiene el registro; si pasa, se baja la duración o se agrega un desafío.
  * La auditoría deja de ser estrictamente de solo inserción: se borra con su dueño.
  * Crear una demo tarda más que registrarse, porque siembra unos cincuenta movimientos: 0,7 s contra PostgreSQL local.
* Riesgos y cómo se mitigan:
  * **La base se llena.** Una demo son 127 filas y unos 35 kB de datos (lo mide un test de integración, que falla si pasa de 100 kB). Aun con los índices triplicando eso, 100 demos ocupan menos de 15 MB de los 500.
  * **Una demo se usa para guardar datos propios.** Vence a las dos horas y el aviso lo dice.
  * **Alguien registra `demo-algo` para hacerse pasar por demo.** El prefijo está reservado.

## Supuestos y datos faltantes

* Se supone que dos horas alcanzan para recorrer la app. Si alguien pide más, se cambia la constante.
* Se supone que el tope de 100 alcanza para el tráfico de un portfolio.

## Referencias

* [ADR-0005](0005-hosting-gratuito.md): hosting sin tareas programadas y con 0,5 GB de base.
* [ADR-0007](0007-autenticacion.md): cuentas, sesiones y límites por origen.
* [ADR-0011](0011-modelo-de-movimientos.md): auditoría de solo inserción.
* Ley 25.326 de Protección de los Datos Personales, art. 16: derecho de supresión.
* PostgreSQL, Advisory Locks: https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS
