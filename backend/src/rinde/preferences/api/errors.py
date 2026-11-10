"""Traduce los errores de preferencias a respuestas HTTP con código estable."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.preferences.domain.errors import PreferencesError


async def preferences_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # Todos son datos inválidos: no hay preferencias que no existan ni ajenas.
    if not isinstance(exc, PreferencesError):
        raise exc
    return JSONResponse({"code": exc.code}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
