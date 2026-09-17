"""Traduce los errores de cuentas a respuestas HTTP con código estable."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.accounts.domain.errors import (
    AccountArchivedError,
    AccountError,
    AccountNotFoundError,
)

# Todo lo que no figure acá es un dato inválido: 422, como la validación de FastAPI.
_STATUS_BY_ERROR: tuple[tuple[type[AccountError], int], ...] = (
    (AccountNotFoundError, status.HTTP_404_NOT_FOUND),
    (AccountArchivedError, status.HTTP_409_CONFLICT),
)


async def accounts_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AccountError):
        raise exc
    status_code = next(
        (code for kind, code in _STATUS_BY_ERROR if isinstance(exc, kind)),
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
    return JSONResponse({"code": exc.code}, status_code=status_code)
