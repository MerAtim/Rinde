# ADR-0036: Mantener despierta la API con un Cron Trigger del Worker

* **Estado:** Aceptado
* **Fecha:** 2026-11-23

## Contexto

La API corre en una instancia gratuita de Render ([ADR-0005](0005-hosting-gratuito.md)). El 22 de noviembre de 2026 la app mostró "Sin conexión con Rinde" durante más de media hora: el borde de Cloudflare que Render pone delante de `onrender.com` respondía `429` con `cf-mitigated: challenge` a todo pedido, incluso al chequeo de vida llamado directo. El pedido nunca llegaba a la API. Se levantó cuando una persona abrió la dirección de Render en un navegador, que resolvió el desafío y despertó el servicio. Un Worker no puede resolver ese desafío.

El PR #142 hizo que la app espere unos 75 segundos con un indicador en lugar de fallar al primer error, pero si el desafío no se levanta solo, la espera termina en el mismo error. El arreglo de fondo es que el servicio no se duerma.

Restricción: no hay presupuesto, así que la solución tiene que ser gratuita.

Hechos verificados el 2026-11-23:

* Render duerme un servicio gratuito "que pasa 15 minutos sin recibir tráfico entrante" y lo despierta en "alrededor de un minuto" con el pedido siguiente.
* Render da "750 horas de instancia gratuita a cada espacio de trabajo por mes calendario"; un servicio dormido no las consume, y si se agotan "suspende todos los servicios web gratuitos hasta el comienzo del mes siguiente".
* Render no menciona prohibiciones sobre mantener despierto un servicio. Sí aclara que las instancias gratuitas no son para aplicaciones en producción y que "puede reiniciar un servicio gratuito en cualquier momento".
* El plan gratuito de Workers admite 5 Cron Triggers por cuenta y 10 ms de CPU por invocación programada; la espera de un `fetch()` no cuenta como CPU.

## Opciones consideradas

### Opción A: Cron Trigger en el Worker de Cloudflare que ya existe

Cada 10 minutos el Worker llama a `/api/health/live`.

* Pros: gratis; usa infraestructura que ya está y se despliega con ella; no suma proveedores ni secretos; el llamado no pasa por internet público hacia un tercero nuevo; si falla, queda en el historial de eventos del Cron Trigger.
* Contras: consume casi todas las horas gratuitas de Render (744 en un mes de 31 días contra 750); usa el plan gratuito de una forma para la que Render no lo pensó.

### Opción B: workflow programado en GitHub Actions

* Pros: gratis en un repositorio público; ya se usa para respaldos.
* Contras: GitHub no garantiza la hora de los `schedule` y en horas de mucha carga los demora o los saltea, así que un intervalo de 10 minutos puede convertirse en 30 y el servicio se duerme igual. Además desactiva los workflows programados de un repositorio sin actividad durante 60 días.

### Opción C: servicio externo de monitoreo (por ejemplo, UptimeRobot)

* Pros: gratis en su plan básico; además avisa si la API cae.
* Contras: suma un proveedor más con una cuenta que administrar y que conoce la dirección privada de la API, que hoy solo está en el Worker y en la CI.

### Opción D: instancia paga de Render

* Pros: es la solución estándar; no duerme y tiene más recursos.
* Contras: cuesta unos 7 dólares por mes, y no hay presupuesto.

### Opción E: no hacer nada

* Pros: sin cambios.
* Contras: la app puede quedar sin servicio cada vez que pasan 15 minutos sin visitas, hasta que alguien la despierte a mano.

## Decisión

Opción A: un Cron Trigger `*/10 * * * *` en el Worker que llama al chequeo de vida. Es la única opción gratuita con hora confiable que no suma proveedores ni expone la dirección de la API.

El llamado no lleva el secreto de origen ([ADR-0032](0032-secreto-entre-worker-y-api.md)): `/api/health/live` es una de las dos rutas que la API atiende sin él, no toca la base y no devuelve datos de nadie. Se manda solo lo necesario. El intervalo de 10 minutos deja 5 de margen frente a los 15 de Render, por si un disparo se demora.

## Consecuencias

* Positivas:
  * La API no se duerme, así que el primer pedido después de una pausa no tarda un minuto ni se topa con el desafío del borde de Render.
  * Neon no se ve afectado: el chequeo de vida no abre conexiones a la base, así que la base sigue suspendiéndose cuando no hay uso.
* Negativas / costos aceptados:
  * Las 750 horas gratuitas alcanzan para un solo servicio despierto todo el mes. Si se agrega otro servicio gratuito en el mismo espacio de trabajo de Render, se agotan y Render suspende todos hasta el mes siguiente.
  * 144 llamados por día a la API que no son de nadie. No dejan línea en el registro de seguridad porque el chequeo de vida no la genera ([ADR-0035](0035-registro-de-eventos-de-seguridad.md)).
  * Usa uno de los 5 Cron Triggers gratuitos de la cuenta de Cloudflare.
* Riesgos y cómo se mitigan:
  * Render cambia las reglas del plan gratuito o empieza a tratar este uso como abuso. Se mitiga revisando su documentación en cada revisión del modelo de amenazas; si pasa, se vuelve a decidir entre las opciones B a D.
  * Render reinicia o duerme el servicio igual y el desafío vuelve. El indicador del PR #142 cubre los casos que se resuelven solos; el resto se ve en el historial del Cron Trigger, que falla con el mensaje del desafío.

## Supuestos y datos faltantes

* Se asume que, con el servicio despierto, el borde de Render no le pide desafíos a los pedidos del Worker. Así fue antes del 22 de noviembre; lo confirma un historial del Cron Trigger sin fallas en los primeros días.
* Se asume que este es el único servicio gratuito del espacio de trabajo de Render. Se confirma en el panel de Render.
* No se encontró documentación de Render ni de Cloudflare que explique por qué el borde pide el desafío al despertar el servicio; el diagnóstico sale de las cabeceras de la respuesta y de reportes de otros proyectos.

## Referencias

* https://render.com/docs/free
* https://developers.cloudflare.com/workers/configuration/cron-triggers/
* https://developers.cloudflare.com/workers/platform/limits/
* https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule
