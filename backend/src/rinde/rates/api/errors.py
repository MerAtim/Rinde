"""Traduce los errores de cotizaciones a respuestas HTTP con código estable."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.rates.domain.errors import RateError, RateNotFoundError, RatesUnavailableError

# Todo lo que no figure acá es un dato inválido: 422, como la validación de FastAPI.
_STATUS_BY_ERROR: tuple[tuple[type[RateError], int], ...] = (
    (RateNotFoundError, status.HTTP_404_NOT_FOUND),
    # El pedido está bien; lo que falla es afuera. Un 503 dice que se puede reintentar.
    (RatesUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE),
)


async def rates_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RateError):
        raise exc
    status_code = next(
        (code for kind, code in _STATUS_BY_ERROR if isinstance(exc, kind)),
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
    return JSONResponse({"code": exc.code}, status_code=status_code)
