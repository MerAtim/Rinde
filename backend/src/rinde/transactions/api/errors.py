"""Traduce los errores de movimientos a respuestas HTTP con código estable."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.shared.domain.errors import DomainError
from rinde.transactions.domain.errors import (
    CategoryInUseError,
    CategoryNameTakenError,
    CategoryNotFoundError,
    IdempotencyKeyReusedError,
    TransactionAccountArchivedError,
    TransactionAccountNotFoundError,
    TransactionNotFoundError,
)

# Todo lo que no figure acá es un dato inválido: 422, como la validación de FastAPI.
_STATUS_BY_ERROR: tuple[tuple[type[DomainError], int], ...] = (
    (TransactionNotFoundError, status.HTTP_404_NOT_FOUND),
    (TransactionAccountNotFoundError, status.HTTP_404_NOT_FOUND),
    (CategoryNotFoundError, status.HTTP_404_NOT_FOUND),
    (TransactionAccountArchivedError, status.HTTP_409_CONFLICT),
    (CategoryInUseError, status.HTTP_409_CONFLICT),
    (CategoryNameTakenError, status.HTTP_409_CONFLICT),
    (IdempotencyKeyReusedError, status.HTTP_409_CONFLICT),
)


async def transactions_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    status_code = next(
        (code for kind, code in _STATUS_BY_ERROR if isinstance(exc, kind)),
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
    return JSONResponse({"code": exc.code}, status_code=status_code)
