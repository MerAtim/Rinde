/**
 * Worker de Cloudflare para producción.
 *
 * Los archivos estáticos del frontend los sirve Cloudflare sin ejecutar este código.
 * Solo /api/* llega acá (run_worker_first en wrangler.jsonc) y se reenvía a la API:
 * para el navegador todo sale del mismo origen, sin CORS y con la CSP en 'self'.
 *
 * ORIGIN_SECRET es un secreto del Worker (wrangler secret put), no una variable:
 * no aparece en el panel ni en la configuración. Le prueba a la API que el
 * pedido pasó por acá (ADR-0032).
 *
 * El Cron Trigger de wrangler.jsonc llama a `scheduled` cada 10 minutos para que
 * Render no duerma la API (ADR-0036).
 */
import { pingApi } from "./keepalive";
import { proxyToApi } from "./proxy";

interface Env {
  API_ORIGIN: string;
  ORIGIN_SECRET: string;
}

export default {
  fetch(request, env) {
    return proxyToApi(request, env.API_ORIGIN, env.ORIGIN_SECRET);
  },
  async scheduled(_controller, env) {
    await pingApi(env.API_ORIGIN);
  },
} satisfies ExportedHandler<Env>;
