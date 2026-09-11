# ADR-0007: Autenticación con usuario, contraseña y código de recuperación

* **Estado:** Aceptado
* **Fecha:** 2026-09-11

## Contexto

La fase 1 agrega cuentas de usuario. Restricciones:

* Costo cero y sin tarjeta (ADR-0005). Render Free bloquea el tráfico saliente a los puertos SMTP 25, 465 y 587 desde septiembre de 2025, y los proveedores de email gratuitos (Resend, Brevo, Mailjet, Postmark) exigen dominio propio o desaconsejan remitentes de webmail. El proyecto todavía no tiene dominio: **no hay forma confiable de enviar emails**.
* Ley 25.326 de Protección de Datos Personales: guardar solo lo necesario.
* NIST SP 800-63B-4 (versión final, 26 de agosto de 2025) para contraseñas usadas como único factor: mínimo 15 caracteres, máximo permitido de al menos 64, sin reglas de composición, sin rotación periódica, comparación obligatoria contra listas de contraseñas comunes o filtradas, y límite obligatorio de intentos fallidos.

## Opciones consideradas

### Identificador
* **Nombre de usuario (elegida):** Rinde no guarda datos personales. Contra: la gente no puede "entrar con su email".
* **Email sin verificar:** familiar, pero cualquiera podría registrarse con el email de otra persona, y es un dato personal más para proteger.

### Recuperación de la cuenta
* **Código de recuperación (elegida):** 20 símbolos Crockford Base32 (100 bits de azar), mostrado una sola vez al registrarse y rotado cada vez que se usa. Contra: si la persona pierde la contraseña y el código, pierde la cuenta.
* **Email:** imposible hoy sin dominio. Se agregará como adaptador de un puerto `EmailSender` cuando exista.

### Sesiones
* **Sesiones opacas en el servidor (elegida):** token de 256 bits en una cookie `__Host-rinde_session` con `HttpOnly`, `Secure`, `SameSite=Strict` y `Path=/`; la base guarda solo su SHA-256. Se revocan al instante (cerrar sesión, recuperar la cuenta).
* **JWT de acceso con refresh rotativo (propuesta original del roadmap):** no se puede revocar un token emitido sin mantener una lista negra, exige administrar claves, y en un monolito de un solo origen no aporta nada.

### Protección contra CSRF
* **`SameSite=Strict` más encabezado propio `X-Requested-With: rinde` (elegida):** otro sitio no puede agregar ese encabezado sin un permiso CORS que la API no otorga (defensa recomendada por OWASP para APIs JSON).
* **Token sincronizado (double submit):** más piezas para el mismo resultado en una API sin formularios HTML.

## Decisión

* **Usuario:** 3 a 30 caracteres, normalizado a minúsculas (NFKC y casefold); letras ASCII, dígitos, punto, guion y guion bajo, sin empezar ni terminar en separador. Lista de nombres reservados.
* **Contraseña:** 15 a 128 caracteres tras normalización NFKC, sin reglas de composición. Se rechaza si contiene el nombre de usuario, si tiene menos de 3 caracteres distintos, o si figura en Pwned Passwords (consulta con k-anonimato: solo viajan los 5 primeros caracteres del SHA-1, con relleno de respuesta).
* **Hash:** argon2id con el mínimo de OWASP (19 MiB, 2 iteraciones, 1 hilo), ajustado a Render Free (0,1 CPU, 512 MB). Se recalcula al iniciar sesión si cambian los parámetros. El hashing corre fuera del bucle de eventos.
* **Límite de intentos:** 10 fallidos por cuenta en 15 minutos; después responde 429 con `Retry-After`. Cuentan también los intentos sobre usuarios inexistentes.
* **Sin enumeración en el inicio de sesión:** el mismo error y el mismo costo de verificación (hash de relleno) exista o no la cuenta. El registro sí revela si un nombre está tomado: es inherente a elegir un nombre de usuario.
* **Sesiones:** duración absoluta de 30 días. Recuperar la cuenta cierra todas las sesiones abiertas.
* **Errores:** códigos estables (`USERNAME_TAKEN`, `PASSWORD_TOO_SHORT`, `INVALID_CREDENTIALS`, `TOO_MANY_ATTEMPTS`, etc.); el frontend los traduce.

## Consecuencias

* Positivas: ningún dato personal almacenado; sesiones revocables; cumplimiento verificable de NIST SP 800-63B-4; el módulo sigue la arquitectura por capas (ADR-0001) y se prueba con adaptadores en memoria.
* Negativas / costos aceptados:
  * Si Pwned Passwords no responde, el control de filtraciones **se omite** (falla abierta) y queda registrado en los logs: se prioriza que la gente pueda registrarse. El largo mínimo de 15 caracteres mitiga el riesgo.
  * Todavía no hay límite de intentos por dirección IP: la API es alcanzable también directamente en Render, y la cadena de proxies (Cloudflare y Render) complica atribuir la IP real. Queda como pendiente.
  * Tampoco hay límite de registros por IP ni CAPTCHA: una persona podría crear muchas cuentas.
  * Los intentos fallidos viejos quedan en la base hasta que se agregue una limpieza periódica.
* Riesgos: pérdida de acceso si se pierden contraseña y código. Mitigación: la pantalla de registro exige confirmar que el código se guardó, y lo ofrece para descargar.

## Referencias

* NIST SP 800-63B-4: https://pages.nist.gov/800-63-4/sp800-63b.html
* OWASP Password Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
* Pwned Passwords API: https://haveibeenpwned.com/API/v3
* Render, bloqueo de SMTP en instancias gratuitas: https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports
