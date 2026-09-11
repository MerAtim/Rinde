"""Defensa contra CSRF para las acciones que cambian estado (ADR-0007)."""

from typing import Annotated

from fastapi import Header

from rinde.auth.domain.errors import AuthError

CSRF_HEADER_VALUE = "rinde"


class CsrfRejectedError(AuthError):
    code = "CSRF_REJECTED"


async def require_csrf_header(x_requested_with: Annotated[str | None, Header()] = None) -> None:
    """Otro sitio no puede agregar este encabezado sin un permiso CORS que la API no otorga."""
    if x_requested_with != CSRF_HEADER_VALUE:
        raise CsrfRejectedError
