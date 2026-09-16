"""Dirección de origen del pedido.

La API corre detrás de dos saltos: el Worker de Cloudflare y el balanceador de
Render. La dirección de la conexión es entonces la del último proxy y no sirve
para contar nada. Cloudflare pone la del visitante en `CF-Connecting-IP` y la
reescribe en su borde, así que quien pase por Cloudflare no puede falsearla.

Límite conocido y aceptado: el origen de Render es alcanzable desde internet,
así que alguien que lo llame directo puede inventar la cabecera. Con eso esquiva
este límite, pero no el límite por cuenta, que no depende de ninguna cabecera.
Cerrarlo del todo pide un secreto compartido entre el Worker y la API, que es
una decisión de despliegue aparte y está anotada en el roadmap.

La dirección se valida antes de usarla: es un dato que viene de afuera y termina
en la base, así que se trata como cualquier otra entrada no confiable.
"""

from ipaddress import ip_address
from typing import Annotated

from fastapi import Depends, Request

# En orden de confianza. X-Forwarded-For puede traer una cadena de direcciones
# separadas por coma; la primera es la del cliente.
FORWARDED_HEADERS = ("cf-connecting-ip", "x-forwarded-for")


def _parse(value: str) -> str | None:
    candidate = value.split(",", maxsplit=1)[0].strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def client_address(request: Request) -> str | None:
    """Devuelve None cuando no se puede determinar; el límite falla abierto."""
    for header in FORWARDED_HEADERS:
        raw = request.headers.get(header)
        if raw and (parsed := _parse(raw)):
            return parsed
    # Sin proxy en el medio, la dirección de la conexión sirve. Se valida igual:
    # solo se guardan direcciones de verdad.
    return _parse(request.client.host) if request.client else None


ClientAddress = Annotated[str | None, Depends(client_address)]
