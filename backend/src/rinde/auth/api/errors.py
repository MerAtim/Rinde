"""Traduce los errores de autenticación a respuestas HTTP con código estable."""

from fastapi import Request, status
from fastapi.responses import JSONResponse

from rinde.auth.domain.errors import (
    AuthError,
    InvalidCredentialsError,
    InvalidRecoveryCodeError,
    NotAuthenticatedError,
    TooManyAttemptsError,
    UsernameTakenError,
)

# Todo lo que no figure acá es un dato inválido: 422, como la validación de FastAPI.
_UNPROCESSABLE = 422
_STATUS_BY_ERROR: tuple[tuple[type[AuthError], int], ...] = (
    (UsernameTakenError, status.HTTP_409_CONFLICT),
    (InvalidCredentialsError, status.HTTP_401_UNAUTHORIZED),
    (InvalidRecoveryCodeError, status.HTTP_401_UNAUTHORIZED),
    (NotAuthenticatedError, status.HTTP_401_UNAUTHORIZED),
    (TooManyAttemptsError, status.HTTP_429_TOO_MANY_REQUESTS),
)


async def auth_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AuthError):
        raise exc
    status_code = next(
        (code for kind, code in _STATUS_BY_ERROR if isinstance(exc, kind)), _UNPROCESSABLE
    )
    headers = (
        {"Retry-After": str(exc.retry_after_seconds)}
        if isinstance(exc, TooManyAttemptsError)
        else None
    )
    return JSONResponse({"code": exc.code}, status_code=status_code, headers=headers)
