"""Endpoints de autenticación (ADR-0007).

Las acciones que cambian estado exigen el encabezado CSRF.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from rinde.auth.api.client import ClientAddress
from rinde.auth.api.cookies import SessionCookie, session_cookie
from rinde.auth.api.dependencies import auth_unit
from rinde.auth.api.schemas import (
    Credentials,
    DeleteAccountRequest,
    DemoResponse,
    MeResponse,
    RecoverRequest,
    RecoverResponse,
    RegisterResponse,
)
from rinde.auth.application.demo import DEMO_TTL
from rinde.auth.application.unit import AuthUnit
from rinde.shared.api.csrf import CSRF
from rinde.shared.api.identity import CurrentUserId
from rinde.shared.api.schemas import error_responses

router = APIRouter(prefix="/auth", tags=["auth"])

Unit = Annotated[AuthUnit, Depends(auth_unit)]
SessionCookieDep = Annotated[SessionCookie, Depends(session_cookie)]


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(403, 409, 422),
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
    responses=error_responses(401, 403, 429),
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
    responses=error_responses(403),
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
    responses=error_responses(401, 403, 422, 429),
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


@router.post(
    "/demo",
    status_code=status.HTTP_201_CREATED,
    dependencies=CSRF,
    responses=error_responses(403, 429, 503),
    summary="Probar la demo",
)
async def start_demo(
    response: Response, unit: Unit, cookie: SessionCookieDep, client: ClientAddress
) -> DemoResponse:
    """Crea una cuenta demo con datos de ejemplo y abre su sesión (ADR-0028).

    La cuenta se borra a las dos horas con todo lo que tenga, y la cookie vence
    con ella. Nadie puede iniciar sesión en una demo: se entra solo así.
    """
    demo = await unit.start_demo.execute(client)
    cookie.set(response, demo.session_token, max_age_seconds=int(DEMO_TTL.total_seconds()))
    return DemoResponse(username=demo.username, demo_expires_at=demo.expires_at)


@router.get("/me", responses=error_responses(401), summary="Cuenta de la sesión actual")
async def me(request: Request, unit: Unit, cookie: SessionCookieDep) -> MeResponse:
    user = await unit.authenticate.execute(cookie.read(request))
    return MeResponse(username=user.username.value, demo_expires_at=user.demo_expires_at)


# POST y no DELETE: la contraseña viaja en el cuerpo, y la RFC 9110 no le da
# significado al cuerpo de un DELETE; un intermediario puede descartarlo.
@router.post(
    "/me/delete",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=CSRF,
    responses=error_responses(401, 403, 409, 422, 429),
    summary="Borrar la cuenta propia con todos sus datos",
)
async def delete_account(  # noqa: PLR0913  (cada parámetro es una dependencia que inyecta FastAPI)
    *,
    payload: DeleteAccountRequest,
    response: Response,
    user_id: CurrentUserId,
    unit: Unit,
    cookie: SessionCookieDep,
    client: ClientAddress,
) -> None:
    """Borra la cuenta y todo lo suyo en el momento, y cierra la sesión (ADR-0034).

    Se confirma con la contraseña. No tiene vuelta atrás: los respaldos cifrados
    la conservan hasta 90 días, y si se restaurara uno, la baja se vuelve a aplicar.
    """
    await unit.delete_account.execute(user_id, payload.password.get_secret_value(), client)
    cookie.clear(response)
