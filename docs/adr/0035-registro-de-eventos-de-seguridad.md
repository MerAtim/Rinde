# ADR-0035: Registro de eventos de seguridad en JSON, con el vocabulario de OWASP

* **Estado:** Aceptado
* **Fecha:** 2026-11-22

## Contexto

OWASP Top 10 2021 pone en el puesto A09 las fallas de registro y monitoreo: sin un registro de los hechos de seguridad, un ataque en curso no se ve y después no se puede reconstruir. OWASP ASVS (V16, registro de seguridad) pide registrar cada intento de autenticación, exitoso o no, los bloqueos y los rechazos de controles de seguridad, sin escribir secretos ni datos de más.

Hasta ahora la API no registraba nada de eso. Los límites por cuenta y por origen frenaban los ataques, pero en silencio: un rociado de contraseñas contra miles de cuentas no dejaba rastro.

Hechos que condicionan la decisión:

* La API corre en Render, que guarda lo que el proceso escribe en la salida estándar y lo muestra con búsqueda en el panel.
* La base es la de Neon en el plan gratuito, con 500 MB.
* El nombre de usuario puede traer una contraseña: es común que alguien la escriba en el campo equivocado. Y la Ley 25.326 (art. 4) pide no tratar más datos personales que los necesarios.
* La dirección IP del visitante es confiable solo si el pedido pasó por el Worker de Cloudflare (ADR-0032).

## Opciones consideradas

### Opción A: líneas JSON en la salida estándar, con el vocabulario de OWASP
* Pros: no agrega dependencias, secretos ni tablas; Render ya las recoge. El OWASP Logging Vocabulary es un estándar publicado: quien audite lee `authn_login_fail:<id>` sin un diccionario propio. JSON escapa los saltos de línea, así que un valor que viene de afuera no puede inventar una línea (CWE-117).
* Contras: la retención depende del plan de Render y no hay alertas automáticas. Si el destino falla, el evento se pierde.

### Opción B: tabla de auditoría de seguridad en la base
* Pros: retención bajo control propio, consultas con SQL.
* Contras: guarda direcciones IP en la misma base que los datos financieros, con su propia política de borrado que mantener. Consume espacio del plan gratuito y suma una escritura a cada intento fallido, que es justo lo que multiplica un ataque. Además, quien comprometa la base puede borrar el rastro de lo que hizo.

### Opción C: mandar los eventos a un servicio externo (SIEM o recolector de logs)
* Pros: retención larga, búsqueda y alertas.
* Contras: otro tercero que recibe datos personales, otro secreto que custodiar y, fuera del plan gratuito, un costo. Para el volumen de hoy es más infraestructura que problema.

## Decisión

Opción A. Es lo estándar, cubre lo que pide ASVS para el tamaño actual del sistema, y pasar a la opción C más adelante no cambia ni el código ni el formato: Render puede reenviar la salida estándar a un recolector por syslog.

Qué se registra, con el nivel que le da el vocabulario:

| Evento | Cuándo | Nivel |
|---|---|---|
| `authn_login_success:<id>` | inicio de sesión correcto | INFO |
| `authn_login_fail[:<id>]` | contraseña incorrecta o cuenta inexistente | WARN |
| `authn_login_lock[:<id>],maxretries` | pedido rechazado por la cuenta bloqueada | WARN |
| `authn_reauth_fail:<id>` | contraseña incorrecta al confirmar el borrado de la cuenta | WARN |
| `authn_password_change:<id>` | contraseña cambiada con el código de recuperación | INFO |
| `authn_password_change_fail[:<id>]` | código de recuperación incorrecto | CRITICAL |
| `excess_rate_limit_exceeded:<acción>,<tope>` | tope por dirección de origen alcanzado | WARN |
| `session_expired:<id>,logout` | cierre de sesión | INFO |
| `session_use_after_expire:<id>` | se usó una sesión vencida | WARN |
| `user_created:<id>[,demo]` | cuenta nueva o demo | WARN |
| `user_deleted:<id>,<id>` | cuenta borrada por su titular | WARN |
| `csrf_rejected` | pedido que cambia estado sin el encabezado CSRF | WARN |
| `origin_rejected` | pedido que no llegó por el Worker | WARN |

Cada línea lleva `datetime` (UTC), `appid`, `event`, `level`, `description` y, cuando corresponde, `source_ip`, `request_method` y `request_uri`. Son los nombres de campo que recomienda el vocabulario, en una lista cerrada: cualquier otro campo se descarta.

Desvíos del vocabulario, cada uno con su motivo:

* **El identificador interno de la cuenta en lugar del nombre de usuario**, por lo dicho en el contexto. El identificador no dice nada fuera de la base. Si la cuenta no existe, el evento va sin identificador.
* **`authn_reauth_fail`, `csrf_rejected` y `origin_rejected` son nombres propios**, con la misma forma, porque el vocabulario no tiene una entrada que les corresponda.
* **`session_use_after_expire` baja de CRITICAL a WARN**: la sesión vence sola a los 30 días, así que lo común es alguien que vuelve después de un tiempo. Si fuera CRITICAL, el nivel que tiene que despertar a alguien perdería sentido.
* **`excess_rate_limit_exceeded` lleva la acción y no la cuenta**: ese límite cuenta por dirección de origen, no por cuenta.

Qué no se registra, a propósito:

* **Un token de sesión desconocido.** Lo manda cualquier navegador con una cookie vieja en cada pedido y llenaría el registro. Adivinar un token de 256 bits no es un ataque que valga la pena contar.
* **Los errores de validación (422) y los pedidos sin sesión (401).** Son el ruido normal de un cliente; los intentos que importan ya quedan como fallas de autenticación.
* **El acceso a un recurso ajeno.** La API responde que no existe (ADR-0009) y, desde adentro, un identificador ajeno no se distingue de uno que no existe.
* **El agente de usuario (`useragent`), los parámetros de la consulta y el cuerpo del pedido.** Son datos de más.
* **La dirección en `origin_rejected`.** Ese pedido no pasó por Cloudflare, así que la cabecera con la dirección la pudo escribir quien llamó.

La garantía de que no se cuela un dato de más no depende del cuidado de quien llama. El puerto `SecurityLog` acepta como parámetros solo identificadores, valores de un enum cerrado y números: mypy rechaza un `str` o un `Username`. Un test recorre todos los casos de uso y verifica que ningún parámetro sea el usuario, una contraseña, un token o el código.

Para registrar la dirección también en el rechazo de CSRF, `client_address` pasa de `auth/api/client.py` al kernel compartido (`shared/api/client.py`). ADR-0032 todavía lo nombra con la ruta anterior.

## Consecuencias

* Positivas:
  * Un ataque de fuerza bruta o de rociado se ve en el panel de Render: cuántos intentos, desde qué direcciones y contra qué cuentas.
  * Después de un incidente se puede reconstruir qué pasó dentro de la ventana de retención.
  * El formato es estándar y se puede reenviar a un recolector sin tocar el código.
* Negativas y costos aceptados:
  * **No hay alertas.** Alguien tiene que mirar el registro. Es el hueco que sigue abierto de A09.
  * **La retención es la del plan de Render**, no una elegida. Pasados esos días, el rastro se pierde.
  * **Las direcciones IP son datos personales.** Se guardan por un interés legítimo, la seguridad de las cuentas, y solo durante la retención de Render.
  * **La escritura es sincrónica**, en el mismo pedido. Con el volumen actual no se nota; si creciera, se pasaría a un `QueueHandler`, como recomienda la documentación de Python para aplicaciones web.
* Riesgos y cómo se mitigan:
  * **Inyección de líneas falsas (CWE-117):** todo se serializa con `json.dumps` y una lista cerrada de campos. Un test manda una ruta con saltos de línea y verifica que sale una sola línea.
  * **Un secreto en el registro:** lo impiden los tipos del puerto, el test que recorre los casos de uso y el que lee la línea real de un inicio de sesión fallido.
  * **Un evento nuevo sin nivel ni descripción:** un test verifica que cada evento del puerto tiene su entrada en el catálogo.

## Supuestos y datos faltantes

* **Se supone que Render guarda el registro 7 días en el plan Hobby**, como dice su documentación de logs. Render cambió sus planes en abril de 2026, así que hay que confirmarlo en el panel. Si fuera menos, conviene reenviar el registro a un recolector (opción C).
* **Se supone que el volumen es bajo.** Si un escáner que golpea el origen de Render llenara el registro con `origin_rejected`, se podría muestrear ese evento.

## Referencias

* OWASP Top 10 2021, A09: Security Logging and Monitoring Failures.
* OWASP Logging Vocabulary Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html
* OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
* OWASP ASVS 5.0, V16: Security Logging and Error Handling.
* CWE-117: Improper Output Neutralization for Logs.
* Render, logs en el panel: https://render.com/docs/logging
* Ley 25.326 de Protección de los Datos Personales, art. 4.
* ADR-0009, ADR-0032.
