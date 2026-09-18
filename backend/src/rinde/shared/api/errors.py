"""Red de seguridad para los errores de dominio que ningún módulo traduce.

Cada módulo traduce los suyos con su propio manejador. Los del kernel
compartido, como los de `Money`, no son de nadie: caen acá y salen como 422 con
su código estable, nunca como un 500 con una traza.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.shared.domain.errors import DomainError


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    return JSONResponse({"code": exc.code}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
