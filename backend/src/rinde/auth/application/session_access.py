"""Casos de uso sobre una sesión existente: identificar la cuenta y cerrar la sesión."""

from rinde.auth.application.dependencies import AuthDependencies
from rinde.auth.application.ports import SecurityDetail, SecurityEvent
from rinde.auth.application.sessions import hash_token
from rinde.auth.domain.errors import NotAuthenticatedError
from rinde.auth.domain.user import User


class AuthenticateSession:
    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def execute(self, token: str | None, client: str | None = None) -> User:
        deps = self._deps
        if not token:
            raise NotAuthenticatedError
        token_hash = hash_token(token)
        session = await deps.sessions.by_token_hash(token_hash)
        # Un token desconocido no se registra: es lo que manda cualquier
        # navegador con una cookie vieja en cada pedido, y llenaría el registro.
        # Adivinar un token de 256 bits no es un ataque que valga la pena contar.
        if session is None:
            raise NotAuthenticatedError
        if session.expires_at <= deps.services.clock.now():
            await deps.sessions.delete(token_hash)
            await deps.transaction.commit()
            # Se registra una sola vez: la sesión vencida se borra acá mismo.
            deps.services.security_log.record(
                SecurityEvent.SESSION_USED_AFTER_EXPIRY, session.user_id, client=client
            )
            raise NotAuthenticatedError
        user = await deps.users.by_id(session.user_id)
        # La sesión de una demo vence con ella; esto cubre una demo vencida que
        # todavía no se borró, aunque la sesión dijera otra cosa.
        if user is None or user.is_expired(deps.services.clock.now()):
            raise NotAuthenticatedError
        return user


class LogoutUser:
    def __init__(self, deps: AuthDependencies) -> None:
        self._deps = deps

    async def execute(self, token: str, client: str | None = None) -> None:
        deps = self._deps
        token_hash = hash_token(token)
        session = await deps.sessions.by_token_hash(token_hash)
        if session is None:
            return
        await deps.sessions.delete(token_hash)
        await deps.transaction.commit()
        deps.services.security_log.record(
            SecurityEvent.SESSION_ENDED, session.user_id, SecurityDetail.LOGOUT, client=client
        )
