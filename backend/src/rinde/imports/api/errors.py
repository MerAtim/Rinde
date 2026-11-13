"""Traduce los errores de importación a respuestas HTTP con código estable."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.imports.domain.errors import (
    ImportBatchNotFoundError,
    ImportFileTooLargeError,
    StatementImportError,
)

# Todo lo que no figure acá es un dato inválido: 422, como la validación de FastAPI.
_STATUS_BY_ERROR: tuple[tuple[type[StatementImportError], int], ...] = (
    (ImportBatchNotFoundError, status.HTTP_404_NOT_FOUND),
    (ImportFileTooLargeError, status.HTTP_413_CONTENT_TOO_LARGE),
)


async def imports_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StatementImportError):
        raise exc
    status_code = next(
        (code for kind, code in _STATUS_BY_ERROR if isinstance(exc, kind)),
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
    return JSONResponse({"code": exc.code}, status_code=status_code)
