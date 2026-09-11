/**
 * Worker de Cloudflare para producción.
 *
 * Los archivos estáticos del frontend los sirve Cloudflare sin ejecutar este código.
 * Solo /api/* llega acá (run_worker_first en wrangler.jsonc) y se reenvía a la API:
 * para el navegador todo sale del mismo origen, sin CORS y con la CSP en 'self'.
 */
import { proxyToApi } from "./proxy";

interface Env {
  API_ORIGIN: string;
}

export default {
  fetch(request, env) {
    return proxyToApi(request, env.API_ORIGIN);
  },
} satisfies ExportedHandler<Env>;
