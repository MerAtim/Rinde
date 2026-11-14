"""Pedidos a las fuentes de cotizaciones, con la política común a toda fuente pública.

La política (tiempo máximo, reintento con espera, tope de tamaño) vive en el
kernel compartido. Acá solo se traduce su error al del puerto de cotizaciones,
que es el que atrapa la cadena de fuentes para pasar a la siguiente.
"""

import httpx

from rinde.rates.application.ports import RateSourceUnavailableError
from rinde.shared.infrastructure import http
from rinde.shared.infrastructure.http import MAX_RESPONSE_BYTES

__all__ = ["MAX_RESPONSE_BYTES", "get_json"]


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout_seconds: float,
    backoff_seconds: float = 0.25,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> object | None:
    """El JSON de la respuesta, con los números como `Decimal`. `None` si es un 404."""
    try:
        return await http.get_json(
            client,
            url,
            timeout_seconds=timeout_seconds,
            backoff_seconds=backoff_seconds,
            max_bytes=max_bytes,
        )
    except http.SourceUnavailableError:
        raise RateSourceUnavailableError(url) from None
