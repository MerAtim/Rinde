"""Defensa contra CSRF para las acciones que cambian estado (ADR-0007).

Vive en el kernel compartido y no en `auth` porque protege a toda la API: cada
módulo que tenga endpoints que cambian estado la necesita, y un módulo no puede
depender de la capa api de otro.
"""

from typing import Annotated, ClassVar

from fastapi import Depends, Header, Request, status
from fastapi.responses import JSONResponse

CSRF_HEADER_VALUE = "rinde"


class CsrfRejectedError(Exception):
    code: ClassVar[str] = "CSRF_REJECTED"


async def require_csrf_header(x_requested_with: Annotated[str | None, Header()] = None) -> None:
    """Otro sitio no puede agregar este encabezado sin un permiso CORS que la API no otorga."""
    if x_requested_with != CSRF_HEADER_VALUE:
        raise CsrfRejectedError


# Para `dependencies=CSRF` en cada endpoint que cambia estado. Lo verifica tests/api/test_csrf.py.
CSRF = [Depends(require_csrf_header)]


async def csrf_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, CsrfRejectedError):
        raise exc
    return JSONResponse({"code": exc.code}, status_code=status.HTTP_403_FORBIDDEN)
