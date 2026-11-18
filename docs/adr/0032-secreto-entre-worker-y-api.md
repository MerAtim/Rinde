# ADR-0032: Solo el Worker habla con la API: un secreto compartido de origen

* **Estado:** Aceptado
* **Fecha:** 2026-11-18

## Contexto

En producción el navegador habla con un Worker de Cloudflare, que reenvía `/api/*` a la API en Render (ADR-0005). Pero el origen de Render tiene su propia dirección pública y responde a cualquiera.

Eso deja un hueco, anotado como límite aceptado en `auth/api/client.py` y en el roadmap:

* La API toma la dirección del visitante de `CF-Connecting-IP`, que Cloudflare reescribe en su borde. Quien llama directo a Render, sin pasar por Cloudflare, puede escribirla a mano.
* Con eso esquiva los límites por dirección: los intentos de inicio de sesión, los registros y las demos (ADR-0007, ADR-0028). El límite por cuenta sigue en pie.
* Una demo crea filas en la base. Sin límite, alguien puede crear demos sin parar y llenar los 0,5 GB de Neon, o mantener ocupada la CPU con argon2 en cada inicio de sesión.
* Directo a Render, tampoco aplica ninguna protección de Cloudflare.

Restricciones: planes gratuitos (ADR-0005). Render Free no filtra el tráfico entrante por dirección ni valida certificados de cliente.

## Opciones consideradas

### Opción A: un secreto compartido en una cabecera
* Pros:
  * Es el patrón que documenta Cloudflare para proteger un origen detrás de un Worker.
  * No depende del proveedor del origen: funciona en Render Free.
  * Se prueba con un test de unidad de cada lado.
* Contras:
  * Un secreto más que guardar en tres lugares (GitHub, Cloudflare y Render) y rotar.
  * Si se filtra, el hueco vuelve hasta rotarlo.

### Opción B: aceptar solo las direcciones de Cloudflare
* Pros: sin secreto.
* Contras:
  * Render Free no permite filtrar por dirección.
  * Aunque se pudiera, no autentica nada: cualquiera con un Worker propio sale por esas mismas direcciones.

### Opción C: Cloudflare Tunnel o certificados de cliente (mTLS)
* Pros: el origen deja de ser público, o exige un certificado que solo tiene Cloudflare.
* Contras: el túnel pide correr `cloudflared` junto a la API, y Render Free no valida certificados de cliente. Ninguno entra en los planes gratuitos actuales.

## Decisión

Opción A. Es la única que cierra el acceso directo con la infraestructura actual.

* El Worker agrega `X-Rinde-Origin` con el secreto a cada pedido, y pisa la que mande el visitante.
* En producción, la API rechaza con 403 (`ORIGIN_REJECTED`) cualquier pedido sin el secreto correcto, comparado en tiempo constante. Quedan afuera `/api/health/live` y `/api/health/ready`, que usan el chequeo de salud de Render y el CD; no devuelven datos de nadie.
* Sin el secreto configurado, la API no arranca en producción: seguro por defecto.
* El secreto tiene al menos 32 caracteres, se genera al azar y vive como secreto en los tres lugares: en el entorno `produccion` de GitHub, en el Worker (`wrangler secret put`, no como variable) y en las variables de entorno de Render. Nunca en el repositorio.

**Despliegue en dos pasos.** El CD despliega la API antes que el Worker. Si los dos cambios fueran juntos, durante unos minutos la API exigiría un secreto que el Worker viejo todavía no manda. Por eso entran en dos PR: primero el Worker empieza a mandarlo, que la API ignora; después la API empieza a exigirlo.

**Rotación sin corte.** La API acepta varios secretos separados por coma:

1. En Render, `nuevo,actual`.
2. En GitHub, el nuevo, y desplegar: el Worker pasa a mandar el nuevo.
3. En Render, solo el nuevo.

## Consecuencias

* Positivas:
  * Los límites por dirección pasan a valer de verdad: la cabecera de dirección solo puede venir de Cloudflare.
  * Todo el tráfico pasa por Cloudflare y por sus protecciones.
  * Se cierra el límite aceptado de `client.py` y la tarea del roadmap.
* Negativas / costos aceptados:
  * Un secreto más que administrar en tres lugares.
  * Probar la API desplegada a mano pide pasar por el Worker.
  * Los dos chequeos de salud quedan abiertos a cualquiera; solo dicen si la API y la base responden.
* Riesgos y cómo se mitigan:
  * **Se filtra el secreto:** se rota con el procedimiento de arriba. GitHub lo oculta en los logs, el Worker lo recibe por la entrada estándar y la API lo guarda como `SecretStr`, que no se imprime.
  * **Falta configurarlo en algún lugar:** el CD frena antes de publicar el Worker, y la API no arranca; Render sigue sirviendo la versión anterior.

## Supuestos y datos faltantes

* Se asume que Cloudflare sigue reescribiendo `CF-Connecting-IP` en los pedidos que el Worker hace al origen, como hasta ahora.

## Referencias

* [ADR-0005](0005-hosting-gratuito.md): hosting gratuito.
* [ADR-0007](0007-autenticacion.md): autenticación y límites de intentos.
* [ADR-0028](0028-cuenta-demo.md): cuenta demo.
* Cloudflare, [Protect your origin server](https://developers.cloudflare.com/fundamentals/security/protect-your-origin-server/).
* OWASP, [API Security Top 10, API8:2023 Security Misconfiguration](https://owasp.org/API-Security/editions/2023/en/0xa8-security-misconfiguration/).
