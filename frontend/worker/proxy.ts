// Cabeceras que se agregan a las respuestas de la API si la API no las define.
// Los datos financieros no se guardan en cachés intermedias: no-store por defecto.
const DEFAULT_HEADERS: Readonly<Record<string, string>> = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
};

/** Traslada ruta y query del pedido entrante al origen de la API. */
export function buildUpstreamUrl(requestUrl: string, apiOrigin: string): URL {
  const incoming = new URL(requestUrl);
  const upstream = new URL(apiOrigin);
  upstream.pathname = incoming.pathname;
  upstream.search = incoming.search;
  return upstream;
}

export async function proxyToApi(request: Request, apiOrigin: string): Promise<Response> {
  if (!apiOrigin) {
    return Response.json({ code: "API_ORIGIN_NOT_CONFIGURED" }, { status: 502 });
  }

  const upstreamResponse = await fetch(
    new Request(buildUpstreamUrl(request.url, apiOrigin), request),
  );

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
