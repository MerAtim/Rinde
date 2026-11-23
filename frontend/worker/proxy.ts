// Cabeceras que se agregan a las respuestas de la API si la API no las define.
// Los datos financieros no se guardan en cachés intermedias: no-store por defecto.
const DEFAULT_HEADERS: Readonly<Record<string, string>> = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
};

/** La cabecera con que la API reconoce que el pedido pasó por el Worker (ADR-0032). */
export const ORIGIN_SECRET_HEADER = "X-Rinde-Origin";

/**
 * Render pone a Cloudflare delante de la API. Si ese borde decide pedir un
 * desafío (sobre todo al despertar un servicio dormido), contesta 429 con esta
 * cabecera y una página HTML: el pedido nunca llegó a la API. Un Worker no puede
 * resolver el desafío, así que se informa como lo que es, un origen que no está
 * disponible por ahora.
 */
const CHALLENGE_HEADER = "cf-mitigated";

/** Segundos que se sugiere esperar antes de reintentar (RFC 9110, sección 10.2.3). */
const RETRY_AFTER_SECONDS = "5";

function unavailable(status: 502 | 503, code: string): Response {
  return Response.json(
    { code },
    { status, headers: { ...DEFAULT_HEADERS, "Retry-After": RETRY_AFTER_SECONDS } },
  );
}

/** Traslada ruta y query del pedido entrante al origen de la API. */
export function buildUpstreamUrl(requestUrl: string, apiOrigin: string): URL {
  const incoming = new URL(requestUrl);
  const upstream = new URL(apiOrigin);
  upstream.pathname = incoming.pathname;
  upstream.search = incoming.search;
  return upstream;
}

export async function proxyToApi(
  request: Request,
  apiOrigin: string,
  originSecret: string,
): Promise<Response> {
  if (!apiOrigin) {
    return Response.json({ code: "API_ORIGIN_NOT_CONFIGURED" }, { status: 502 });
  }
  // Sin secreto no se reenvía nada: la API lo rechazaría, y es mejor que el
  // error diga qué falta configurar.
  if (!originSecret) {
    return Response.json({ code: "ORIGIN_SECRET_NOT_CONFIGURED" }, { status: 502 });
  }

  const upstream = new Request(buildUpstreamUrl(request.url, apiOrigin), request);
  // set y no append: si el visitante mandó su propia cabecera, se pisa.
  upstream.headers.set(ORIGIN_SECRET_HEADER, originSecret);
  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(upstream);
  } catch {
    // Sin respuesta del origen: un error con código estable en vez de la
    // página genérica de Cloudflare.
    return unavailable(502, "API_UNREACHABLE");
  }
  if (upstreamResponse.headers.get(CHALLENGE_HEADER) === "challenge") {
    return unavailable(503, "API_UNAVAILABLE");
  }

  const headers = new Headers(upstreamResponse.headers);
  for (const [name, value] of Object.entries(DEFAULT_HEADERS)) {
    if (!headers.has(name)) {
      headers.set(name, value);
    }
  }
  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers,
  });
}
