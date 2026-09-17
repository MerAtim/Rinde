"""Endpoints de autenticación (ADR-0007).

Las acciones que cambian estado exigen el encabezado CSRF.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status

from rinde.auth.api.client import ClientAddress
from rinde.auth.api.cookies import SessionCookie, session_cookie
from rinde.auth.api.dependencies import auth_unit
from rinde.auth.api.schemas import (
    Credentials,
    ErrorResponse,
    MeResponse,
    RecoverRequest,
    RecoverResponse,
    RegisterResponse,
)
from rinde.auth.application.unit import AuthUnit
from rinde.shared.api.csrf import CSRF

router = APIRouter(prefix="/auth", tags=["auth"])

Unit = Annotated[AuthUnit, Depends(auth_unit)]
SessionCookieDep = Annotated[SessionCookie, Depends(session_cookie)]


def _errors(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: {"model": ErrorResponse} for code in status_codes}


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=_errors(403, 409, 422),
    summary="Crear una cuenta",
)
async def register(
    payload: Credentials,
    response: Response,
    unit: Unit,
    cookie: SessionCookieDep,
    client: ClientAddress,
) -> RegisterResponse:
    registration = await unit.register.execute(
        payload.username, payload.password.get_secret_value(), client
    )
    cookie.set(response, registration.session_token)
    return RegisterResponse(
        username=registration.user.username.value,
        recovery_code=registration.recovery_code,
    )


@router.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=CSRF,
    responses=_errors(401, 403, 429),
    summary="Iniciar sesión",
)
async def login(
    payload: Credentials,
    response: Response,
    unit: Unit,
    cookie: SessionCookieDep,
    client: ClientAddress,
) -> None:
    token = await unit.login.execute(payload.username, payload.password.get_secret_value(), client)
    cookie.set(response, token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=CSRF,
    responses=_errors(403),
    summary="Cerrar sesión",
)
async def logout(
    request: Request, response: Response, unit: Unit, cookie: SessionCookieDep
) -> None:
    token = cookie.read(request)
    if token:
        await unit.logout.execute(token)
    cookie.clear(response)


@router.post(
    "/recover",
    dependencies=CSRF,
    responses=_errors(401, 403, 422, 429),
    summary="Recuperar la cuenta con el código de recuperación",
)
async def recover(
    payload: RecoverRequest,
    response: Response,
    unit: Unit,
    cookie: SessionCookieDep,
    client: ClientAddress,
) -> RecoverResponse:
    recovery = await unit.recover.execute(
        payload.username,
        payload.recovery_code.get_secret_value(),
        payload.new_password.get_secret_value(),
        client,
    )
    cookie.set(response, recovery.session_token)
    return RecoverResponse(recovery_code=recovery.recovery_code)


@router.get("/me", responses=_errors(401), summary="Cuenta de la sesión actual")
async def me(request: Request, unit: Unit, cookie: SessionCookieDep) -> MeResponse:
    user = await unit.authenticate.execute(cookie.read(request))
    return MeResponse(username=user.username.value)
