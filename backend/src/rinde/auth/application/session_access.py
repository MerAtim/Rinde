"""Casos de uso sobre una sesión existente: identificar la cuenta y cerrar la sesión."""

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.sessions import hash_token
from rinde.auth.domain.errors import NotAuthenticatedError
from rinde.auth.domain.user import User


class AuthenticateSession:
    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def execute(self, token: str | None) -> User:
        deps = self._deps
        if not token:
            raise NotAuthenticatedError
        token_hash = hash_token(token)
        session = await deps.sessions.by_token_hash(token_hash)
        if session is None:
            raise NotAuthenticatedError
        if session.expires_at <= deps.services.clock.now():
            await deps.sessions.delete(token_hash)
            await deps.transaction.commit()
            raise NotAuthenticatedError
        user = await deps.users.by_id(session.user_id)
        if user is None:
            raise NotAuthenticatedError
        return user


class LogoutUser:
    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def execute(self, token: str) -> None:
        await self._deps.sessions.delete(hash_token(token))
        await self._deps.transaction.commit()
