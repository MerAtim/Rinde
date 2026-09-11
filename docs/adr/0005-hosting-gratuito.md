# ADR-0005: Hosting gratuito con Cloudflare, Render y Neon

* **Estado:** Aceptado
* **Fecha:** 2026-09-11

## Contexto

La aplicación tiene que estar publicada desde la fase 0 para que el portfolio se pueda ver funcionando. Restricción dura: **costo cero y sin tarjeta de crédito**. Hay tres piezas: frontend estático, API en contenedor Docker y PostgreSQL.

Hechos relevados en la documentación oficial (septiembre de 2026):

* Render Free: 750 horas de instancia por mes; la instancia se apaga tras 15 minutos sin tráfico y tarda alrededor de un minuto en volver. Admite imágenes Docker de registros públicos. El pre-deploy command es solo para instancias pagas. Su PostgreSQL gratuito se elimina a los 30 días.
* Neon Free: 0,5 GB por proyecto, 100 CU-horas por mes, suspensión tras 5 minutos de inactividad, sin tarjeta y sin vencimiento.
* Cloudflare Workers Free: los pedidos a archivos estáticos son gratuitos e ilimitados; 100.000 invocaciones de Worker por día.
* Supabase Free pausa el proyecto tras 7 días de inactividad. Netlify Free cobra créditos por cada despliegue. Fly.io exige tarjeta. Koyeb no ofrece cómputo gratuito.

## Opciones consideradas

### Opción A: Cloudflare Workers (frontend y proxy) + Render (API) + Neon (base)
* Pros: los tres gratuitos y sin tarjeta; frontend servido desde CDN sin demora; el Worker hace de proxy de `/api/*`, así el navegador ve un único origen (sin CORS, CSP `'self'` intacta); la base no vence.
* Contras: tres proveedores que administrar; la API se duerme y el primer pedido tarda cerca de un minuto.

### Opción B: todo en Render (sitio estático, API y PostgreSQL)
* Pros: un solo proveedor.
* Contras: la base gratuita se elimina a los 30 días; inaceptable para una aplicación que guarda datos.

### Opción C: Render + Supabase
* Pros: Supabase suma autenticación y panel propios.
* Contras: pausa tras 7 días sin uso, esperable en un portfolio; esas funciones extra no se usan (la autenticación es propia, ADR-0001).

### Opción D: Fly.io, Google Cloud Run u Oracle Cloud
* Pros: más recursos o sin suspensión.
* Contras: exigen tarjeta de crédito; quedan fuera de la restricción.

## Decisión

Opción A, con la API y la base en la misma región (AWS us-east-2, Ohio) para minimizar la latencia entre ambas, que es la que se multiplica en cada pedido. PostgreSQL 18 en Neon, la misma versión que en local y en CI.

Despliegue continuo desde GitHub Actions al integrar en `main`, en este orden:

1. Construir la imagen de la API y escanearla con Trivy.
2. Publicarla en GitHub Container Registry y desplegar **por digest**: se despliega exactamente la imagen escaneada.
3. Ejecutar las migraciones contra Neon (Render Free no ofrece pre-deploy command).
4. Disparar el deploy hook de Render con esa imagen.
5. Publicar el frontend en Cloudflare.
6. Prueba de humo contra la URL pública.

Los secretos viven en el entorno `produccion` de GitHub, que solo puede usar la rama `main`.

## Consecuencias

* Positivas: costo cero; mismo origen para frontend y API, igual que en local; la imagen que corre en producción es la que pasó el escaneo.
* Negativas / costos aceptados: primer pedido lento tras 15 minutos de inactividad (documentado en el README); tres paneles de proveedores; las migraciones corren antes que el código nuevo, por lo que deben ser compatibles hacia atrás (patrón expandir y contraer).
* Riesgos: los planes gratuitos cambian o desaparecen (ya ocurrió con Fly.io y Koyeb). Mitigación: todo corre en contenedores configurados por variables de entorno; mudarse es cambiar URLs y secretos, no código.

## Supuestos y datos faltantes

* Memoria de la instancia Free de Render: no figura en la documentación consultada; se verifica al crear el servicio.
* Servicios opcionales de Neon (almacenamiento de objetos, funciones, autenticación) quedan desactivados: no se usan y cada uno suma superficie que cuidar.

## Referencias

* https://render.com/docs/free
* https://render.com/docs/deploys
* https://render.com/docs/deploy-an-image
* https://neon.com/pricing
* https://developers.cloudflare.com/workers/platform/pricing/
* https://developers.cloudflare.com/workers/static-assets/routing/worker-script/
