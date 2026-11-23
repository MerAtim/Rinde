/**
 * Mantiene despierta la API (ADR-0036).
 *
 * Render Free duerme el servicio tras 15 minutos sin tráfico entrante, y al
 * despertarlo su borde de Cloudflare puede pedir un desafío que un Worker no
 * resuelve. Un Cron Trigger llama cada 10 minutos al chequeo de vida, así el
 * servicio no llega a dormirse.
 */

/**
 * El chequeo de vida: no toca la base ni devuelve datos de nadie, y la API lo
 * atiende sin el secreto de origen. Por eso no se manda: no hace falta.
 */
export const KEEPALIVE_PATH = "/api/health/live";

/** Si estaba dormida, despertarla tarda cerca de un minuto: se le da margen. */
export const KEEPALIVE_TIMEOUT_MS = 90_000;

/**
 * Hace el llamado y falla si no hubo una respuesta correcta. El error queda en
 * el historial de eventos del Cron Trigger en Cloudflare, que es donde se mira.
 */
export async function pingApi(apiOrigin: string): Promise<void> {
  if (!apiOrigin) {
    throw new Error("API_ORIGIN no está configurado");
  }
  const response = await fetch(new URL(KEEPALIVE_PATH, apiOrigin), {
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(KEEPALIVE_TIMEOUT_MS),
  });
  if (!response.ok) {
    const challenged = response.headers.get("cf-mitigated") === "challenge";
    throw new Error(
      challenged
        ? `La API no respondió: el borde de Render pidió un desafío (${String(response.status)})`
        : `La API respondió ${String(response.status)}`,
    );
  }
}
