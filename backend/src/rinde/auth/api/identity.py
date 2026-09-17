"""Resolvedor de identidad que la raíz de composición registra para toda la API."""

from uuid import UUID

from fastapi import Request

from rinde.auth.api.cookies import SessionCookie
from rinde.auth.application.unit import AuthUnitFactory


async def identify_user(request: Request) -> UUID:
    """Devuelve el usuario de la sesión o lanza NotAuthenticatedError (401)."""
    factory: AuthUnitFactory = request.app.state.auth_factory
    cookie: SessionCookie = request.app.state.session_cookie
    async with factory() as unit:
        user = await unit.authenticate.execute(cookie.read(request))
    return user.id
