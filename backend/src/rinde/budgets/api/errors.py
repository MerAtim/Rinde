"""Traduce los errores de presupuestos a respuestas HTTP con código estable."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.budgets.domain.errors import (
    BudgetCategoryNotFoundError,
    BudgetError,
    BudgetNotFoundError,
)

# Todo lo que no figure acá es un dato inválido: 422, como la validación de FastAPI.
_NOT_FOUND = (BudgetNotFoundError, BudgetCategoryNotFoundError)


async def budgets_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, BudgetError):
        raise exc
    status_code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, _NOT_FOUND)
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return JSONResponse({"code": exc.code}, status_code=status_code)
