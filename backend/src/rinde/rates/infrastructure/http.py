"""Pedidos a las fuentes de cotizaciones: tiempo máximo, reintento con espera y validación.

Todo lo que responde una fuente se trata como un dato que no es de fiar: puede
llegar tarde, vacío, enorme o con otra forma. Ninguno de esos casos llega al
dominio; acá se convierten en `RateSourceUnavailableError`.
"""

import asyncio
import json
from decimal import Decimal

import httpx

from rinde.rates.application.ports import RateSourceUnavailableError

# Errores de un servidor que puede responder bien al rato. Un 429 no se
# reintenta: si la fuente pide que se baje el ritmo, se pasa a la siguiente.
_RETRYABLE_STATUS = frozenset({502, 503, 504})
# Las respuestas reales pesan unos pocos KB. Algo mucho más grande no es una cotización.
MAX_RESPONSE_BYTES = 256 * 1024


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout_seconds: float,
    attempts: int = 2,
    backoff_seconds: float = 0.25,
) -> object | None:
    """El JSON de la respuesta, con los números como `Decimal`. `None` si es un 404.

    Con `float` 1587.9 ya no es exacto antes de llegar al dominio.
    """
    for attempt in range(attempts):
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
        if len(response.content) > MAX_RESPONSE_BYTES:
            break
        try:
            body: object = json.loads(response.content, parse_float=Decimal, parse_int=Decimal)
        except ValueError:
            break
        return body
    raise RateSourceUnavailableError(url)
