"""Pedidos a fuentes públicas: tiempo máximo, reintento con espera y validación.

Todo lo que responde una fuente se trata como un dato que no es de fiar: puede
llegar tarde, vacío, enorme o con otra forma. Ninguno de esos casos sale de
acá como otra cosa que `SourceUnavailableError`, y cada módulo lo traduce al
error de su propio puerto.
"""

import asyncio
import json
from decimal import Decimal

import httpx

# Errores de un servidor que puede responder bien al rato. Un 429 no se
# reintenta: si la fuente pide que se baje el ritmo, se le hace caso.
_RETRYABLE_STATUS = frozenset({502, 503, 504})
# Las respuestas reales pesan unos pocos KB. Algo mucho más grande no es un dato.
MAX_RESPONSE_BYTES = 256 * 1024
# Un reintento: una fuente caída no hace esperar de más.
ATTEMPTS = 2


class SourceUnavailableError(Exception):
    """La fuente no respondió, o respondió algo que no se puede usar."""


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout_seconds: float,
    backoff_seconds: float = 0.25,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> object | None:
    """El JSON de la respuesta, con los números como `Decimal`. `None` si es un 404.

    Con `float` 1587.9 ya no es exacto antes de llegar al dominio.
    """
    for attempt in range(ATTEMPTS):
        if attempt:
            await asyncio.sleep(backoff_seconds * 2 ** (attempt - 1))
        try:
            response = await client.get(url, timeout=timeout_seconds)
        except httpx.TransportError:
            continue
        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.status_code in _RETRYABLE_STATUS:
            continue
        if not response.is_success:
            break
        if len(response.content) > max_bytes:
            break
        try:
            body: object = json.loads(response.content, parse_float=Decimal, parse_int=Decimal)
        except ValueError:
            break
        return body
    raise SourceUnavailableError(url)
